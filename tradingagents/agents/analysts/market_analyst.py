from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import sys

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_crypto_market_snapshot,
    get_compact_report_instruction,
    get_indicators,
    get_language_instruction,
    get_stock_data,
    get_time_context_from_state,
)
from tradingagents.agents.utils.crypto_data_tools import (
    build_crypto_market_snapshot,
    format_crypto_market_snapshot,
    normalize_crypto_market_symbol,
)
from tradingagents.agents.schemas import parse_analyst_feature_summary


CORE_INDICATORS = (
    "close_10_ema",
    "close_50_sma",
    "close_200_sma",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "atr",
    "boll_ub",
    "boll_lb",
)


def _has_unavailable_marker(text: object) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return True
    markers = (
        "unavailable",
        "no data",
        "not found",
        "rate limit",
        "error",
        "failed",
    )
    return any(marker in normalized for marker in markers)


def _should_enable_market_tools(market_context: dict[str, object]) -> bool:
    if _has_unavailable_marker(market_context.get("price_block")):
        return True
    if _has_unavailable_marker(market_context.get("indicator_block")):
        return True
    if market_context.get("asset_type") == "crypto":
        snapshot = market_context.get("crypto_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("available") is False:
            return True
    return False


def _build_market_evidence_ledger(market_context: dict[str, str]) -> dict:
    indicator_block = market_context.get("indicator_block", "")
    unavailable_lines = [
        line.strip()
        for line in str(indicator_block).splitlines()
        if "unavailable" in line.lower()
    ]
    sources = [
        "get_stock_data",
        "get_indicators",
    ]
    if market_context.get("crypto_snapshot"):
        sources.append("get_crypto_market_snapshot")
    crypto_snapshot = market_context.get("crypto_snapshot") or {}
    derivatives_snapshot = (
        crypto_snapshot.get("derivatives_snapshot", {})
        if isinstance(crypto_snapshot, dict)
        else {}
    )
    data_quality_flags = list(unavailable_lines[:10])
    if isinstance(crypto_snapshot, dict):
        data_quality_flags.extend(crypto_snapshot.get("risk_flags", []) or [])
    if isinstance(derivatives_snapshot, dict) and not derivatives_snapshot.get("available", False):
        data_quality_flags.append("crypto_derivatives_unavailable")
    return {
        "asset_type": market_context.get("asset_type", "stock"),
        "market_symbol": market_context.get("market_symbol"),
        "price_window": {
            "start_date": market_context.get("start_date"),
            "end_date": market_context.get("end_date"),
        },
        "sources": sources,
        "core_indicators": list(CORE_INDICATORS),
        "data_quality_flags": list(dict.fromkeys(data_quality_flags)),
        "has_price_block": bool(str(market_context.get("price_block", "")).strip()),
        "tool_fallback_enabled": _should_enable_market_tools(market_context),
        "crypto_snapshot": crypto_snapshot,
        "crypto_derivatives_snapshot": derivatives_snapshot,
    }


def _prefetch_market_context(state: dict) -> dict[str, str]:
    """Fetch price and indicator data deterministically before the LLM runs."""
    time_context = get_time_context_from_state(state)
    ticker = state["company_of_interest"]
    asset_type = state.get("asset_type", "stock")
    market_symbol = (
        normalize_crypto_market_symbol(ticker)
        if asset_type == "crypto"
        else ticker
    )
    lookback_days = time_context.analysis_lookback_days
    start_date = time_context.price_start_date(lookback_days)
    end_date = time_context.as_of_date
    print(
        f"[market-prefetch] ticker={ticker} market_symbol={market_symbol} start={start_date} end={end_date}",
        file=sys.stderr,
    )

    try:
        price_block = get_stock_data.func(market_symbol, start_date, end_date)
        preview = str(price_block).splitlines()[0] if str(price_block).splitlines() else "<empty>"
        print(
            f"[market-prefetch] price_block={preview[:180]}",
            file=sys.stderr,
        )
    except Exception as exc:
        price_block = f"Price data unavailable: {exc}"
        print(
            f"[market-prefetch] price_error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
    indicator_blocks = []
    for indicator in CORE_INDICATORS:
        try:
            block = get_indicators.func(market_symbol, indicator, end_date, lookback_days)
            indicator_blocks.append(block)
            preview = str(block).splitlines()[0] if str(block).splitlines() else "<empty>"
            print(
                f"[market-prefetch] indicator={indicator} preview={preview[:180]}",
                file=sys.stderr,
            )
        except Exception as exc:
            indicator_blocks.append(f"## {indicator}\nUnavailable: {exc}")
            print(
                f"[market-prefetch] indicator_error={indicator} {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    crypto_snapshot = {}
    crypto_snapshot_block = ""
    if asset_type == "crypto":
        try:
            crypto_snapshot = build_crypto_market_snapshot(ticker, end_date, max(lookback_days, 60))
            crypto_snapshot_block = format_crypto_market_snapshot(crypto_snapshot)
            preview = crypto_snapshot_block.splitlines()[0] if crypto_snapshot_block else "<empty>"
            print(
                f"[market-prefetch] crypto_snapshot={preview[:180]}",
                file=sys.stderr,
            )
        except Exception as exc:
            crypto_snapshot = {
                "symbol": ticker,
                "market_symbol": market_symbol,
                "available": False,
                "risk_flags": ["crypto_snapshot_error"],
                "summary": f"Crypto market snapshot unavailable: {type(exc).__name__}: {exc}",
            }
            crypto_snapshot_block = format_crypto_market_snapshot(crypto_snapshot)
            print(
                f"[market-prefetch] crypto_snapshot_error={type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    return {
        "asset_type": asset_type,
        "market_symbol": market_symbol,
        "start_date": start_date,
        "end_date": end_date,
        "price_block": price_block,
        "indicator_block": "\n\n".join(indicator_blocks),
        "crypto_snapshot": crypto_snapshot,
        "crypto_snapshot_block": crypto_snapshot_block,
    }


def create_market_analyst(llm):
    def market_analyst_node(state):
        time_context = get_time_context_from_state(state)
        market_context = _prefetch_market_context(state)
        asset_type = state.get("asset_type", "stock")
        instrument_context = build_instrument_context(
            state["company_of_interest"], asset_type
        ) + " " + time_context.to_prompt_string()

        crypto_instruction = ""
        if asset_type == "crypto":
            crypto_instruction = (
                " This is a crypto asset. Do not discuss company balance sheet, cash flow, earnings, "
                "or valuation multiples. Add crypto-native analysis: 24/7 trading regime, realized volatility, "
                "drawdown, liquidity/volume confirmation, derivatives funding/open-interest/long-short context, "
                "event/news sensitivity, and risk controls. If derivatives data is unavailable, state that as a "
                "data-quality limitation and do not infer crowding, liquidation pressure, or positioning from silence. "
                "Use user-friendly wording for missing provider data, such as 'derivatives positioning data is "
                "temporarily unavailable', instead of emphasizing raw API errors."
            )

        system_message = (
            "You are a trading assistant tasked with analyzing market structure and technical conditions. "
            "A deterministic prefetch step has already collected the relevant OHLCV window and a compact set "
            "of core indicators for you. Do not invent missing data. If a block says data is unavailable or "
            "rate limited, explicitly say so and lower confidence. Focus on trend, momentum, volatility, and "
            "support/resistance behavior. Use the actual fetched evidence to explain whether the market setup "
            "is constructive, neutral, or deteriorating."
            + crypto_instruction
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_compact_report_instruction()
            + get_language_instruction()
        )
        tools = [get_stock_data, get_indicators]
        if asset_type == "crypto":
            tools.append(get_crypto_market_snapshot)
        use_tools = _should_enable_market_tools(market_context)
        if use_tools:
            system_message += (
                " Some pre-fetched market data is missing or degraded. You may call the provided tools, "
                "but only to fill those specific gaps. If tool results are already present in the message "
                "history, synthesize the final report instead of calling more tools."
            )

        user_message = f"""Analyze the following market data for {state["company_of_interest"]}.

Price window:
- Start date: {market_context["start_date"]}
- End date: {market_context["end_date"]}
- Market-data symbol used: {market_context["market_symbol"]}

OHLCV data:
<start_of_price_data>
{market_context["price_block"]}
<end_of_price_data>

Core indicators:
<start_of_indicator_data>
{market_context["indicator_block"]}
<end_of_indicator_data>

Crypto-native snapshot:
<start_of_crypto_snapshot>
{market_context["crypto_snapshot_block"] or "Not applicable for non-crypto assets."}
<end_of_crypto_snapshot>

Write a detailed technical market report grounded in these fetched results. Explain:
1. Trend direction and moving-average structure
2. Momentum via MACD and RSI
3. Volatility and risk via ATR / Bollinger behavior
4. Whether the setup supports bullish, bearish, or neutral positioning
5. For crypto assets, how volatility, drawdown, and liquidity change the position sizing/risk view
6. Any missing or degraded data that reduces confidence

After the full report, append exactly one machine-readable summary block:

FEATURE_SUMMARY
SCORE: <value from -1.00 to 1.00>
CONFIDENCE: <value from 0.00 to 1.00>
KEY_SIGNAL: <concise market regime signal>
RISK_FLAG: <main technical risk or data caveat>
END_FEATURE_SUMMARY
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("user", "{user_message}"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=time_context.as_of_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(user_message=user_message)

        chain = prompt | (llm.bind_tools(tools) if use_tools else llm)
        result = chain.invoke(state["messages"])
        report = "" if getattr(result, "tool_calls", None) else result.content
        features = parse_analyst_feature_summary(report).model_dump() if report else {}
        evidence_ledger = _build_market_evidence_ledger(market_context)

        return {
            "messages": [result],
            "market_report": report,
            "market_features": features,
            "market_evidence_ledger": evidence_ledger,
        }

    return market_analyst_node
