from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import sys

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_language_instruction,
    get_stock_data,
    get_time_context_from_state,
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


def _prefetch_market_context(state: dict) -> dict[str, str]:
    """Fetch price and indicator data deterministically before the LLM runs."""
    time_context = get_time_context_from_state(state)
    ticker = state["company_of_interest"]
    start_date = time_context.price_start_date(30)
    end_date = time_context.as_of_date
    print(
        f"[market-prefetch] ticker={ticker} start={start_date} end={end_date}",
        file=sys.stderr,
    )

    try:
        price_block = get_stock_data.func(ticker, start_date, end_date)
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
            block = get_indicators.func(ticker, indicator, end_date, 30)
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

    return {
        "start_date": start_date,
        "end_date": end_date,
        "price_block": price_block,
        "indicator_block": "\n\n".join(indicator_blocks),
    }


def create_market_analyst(llm):
    def market_analyst_node(state):
        time_context = get_time_context_from_state(state)
        market_context = _prefetch_market_context(state)
        asset_type = state.get("asset_type", "stock")
        instrument_context = build_instrument_context(
            state["company_of_interest"], asset_type
        ) + " " + time_context.to_prompt_string()

        system_message = (
            "You are a trading assistant tasked with analyzing market structure and technical conditions. "
            "A deterministic prefetch step has already collected the relevant OHLCV window and a compact set "
            "of core indicators for you. Do not invent missing data. If a block says data is unavailable or "
            "rate limited, explicitly say so and lower confidence. Focus on trend, momentum, volatility, and "
            "support/resistance behavior. Use the actual fetched evidence to explain whether the market setup "
            "is constructive, neutral, or deteriorating."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_language_instruction()
        )

        user_message = f"""Analyze the following market data for {state["company_of_interest"]}.

Price window:
- Start date: {market_context["start_date"]}
- End date: {market_context["end_date"]}

OHLCV data:
<start_of_price_data>
{market_context["price_block"]}
<end_of_price_data>

Core indicators:
<start_of_indicator_data>
{market_context["indicator_block"]}
<end_of_indicator_data>

Write a detailed technical market report grounded in these fetched results. Explain:
1. Trend direction and moving-average structure
2. Momentum via MACD and RSI
3. Volatility and risk via ATR / Bollinger behavior
4. Whether the setup supports bullish, bearish, or neutral positioning
5. Any missing or degraded data that reduces confidence

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

        chain = prompt | llm
        result = chain.invoke(state["messages"])
        features = parse_analyst_feature_summary(result.content)

        return {
            "messages": [result],
            "market_report": result.content,
            "market_features": features.model_dump(),
        }

    return market_analyst_node
