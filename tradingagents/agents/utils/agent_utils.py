import re

from langchain_core.messages import HumanMessage, RemoveMessage
from tradingagents.core.time_context import TimeContext, coerce_time_context

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.crypto_data_tools import (
    get_crypto_market_snapshot,
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def get_compact_report_instruction() -> str:
    """Prompt guardrail for analyst reports that feed later agents."""
    return (
        " Keep the report dense and decision-useful: at most 6 short sections, "
        "at most 6 table rows, and no repeated background narrative. Preserve "
        "specific numbers, catalysts, risks, and data caveats."
    )


def build_instrument_context(ticker: str, asset_type: str = "stock") -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    instrument_label = "asset" if asset_type == "crypto" else "instrument"
    extra_hint = (
        " Treat it as a crypto asset rather than a company, and do not assume company fundamentals are available."
        if asset_type == "crypto"
        else ""
    )
    return (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
        + extra_hint
    )


def get_time_context_from_state(state: dict) -> TimeContext:
    """Read a unified time context from the current graph state."""
    trade_date = str(state.get("trade_date", ""))
    return coerce_time_context(state.get("time_context"), trade_date)


def get_time_context_instruction(state: dict) -> str:
    """Render the time context as a prompt instruction."""
    return get_time_context_from_state(state).to_prompt_string()


def build_compact_feature_context(state: dict) -> str:
    """Render analyst feature summaries into a compact prompt block."""
    feature_map = [
        ("Market", state.get("market_features", {})),
        ("Fundamentals", state.get("fundamentals_features", {})),
        ("Sentiment", state.get("sentiment_features", {})),
        ("News", state.get("news_features", {})),
    ]
    lines = ["Structured analyst feature summaries:"]
    for label, features in feature_map:
        if not isinstance(features, dict) or not features:
            lines.append(f"- {label}: unavailable")
            continue
        score = features.get("score", 0.0)
        confidence = features.get("confidence", 0.0)
        key_signal = features.get("key_signal", "n/a")
        risk_flag = features.get("risk_flag", "n/a")
        lines.append(
            f"- {label}: score={score}, confidence={confidence}, "
            f"key_signal={key_signal}, risk_flag={risk_flag}"
        )
    return "\n".join(lines)


def build_data_quality_context(state: dict) -> str:
    """Render a compact view of data quality and source caveats for debate agents."""
    sentiment_ledger = state.get("sentiment_evidence_ledger", {})
    news_ledger = state.get("news_evidence_ledger", {})
    market_ledger = state.get("market_evidence_ledger", {})
    fundamentals_ledger = state.get("fundamentals_evidence_ledger", {})

    lines = ["Data quality and source consistency summary:"]
    if market_ledger:
        flags = market_ledger.get("data_quality_flags", [])
        lines.append(f"- Market: flags={flags or 'none'}")
    if sentiment_ledger:
        lines.append(
            f"- Sentiment: coverage={sentiment_ledger.get('source_coverage', 0.0)}, "
            f"quality_weight={sentiment_ledger.get('quality_weight', 0.0)}, "
            f"flags={sentiment_ledger.get('quality_flags', []) or 'none'}"
        )
        if sentiment_ledger.get("source_sample_counts"):
            lines.append(f"- Sentiment sample counts: {sentiment_ledger['source_sample_counts']}")
    if news_ledger:
        lines.append(
            f"- News: source_count={news_ledger.get('source_count', 0)}, "
            f"source_diversity={news_ledger.get('source_diversity', 0)}"
        )
    if fundamentals_ledger:
        lines.append(
            f"- Fundamentals: sources={fundamentals_ledger.get('sources', [])}, "
            f"lookback_days={fundamentals_ledger.get('lookback_days', 0)}"
        )
    return "\n".join(lines)


def build_quant_summary_context(state: dict) -> str:
    """Render the core quant and execution numbers as a compact debate aid."""
    factor_score = state.get("factor_score", {})
    position_sizing = state.get("position_sizing", {})
    risk_gate = state.get("risk_gate_result", {})
    alpha_summary = state.get("alpha_experience_summary", {})
    execution_plan = state.get("execution_plan", {})

    lines = ["Quant summary:"]
    if factor_score:
        lines.append(
            f"- Factor composite={factor_score.get('composite_score', 0.0)}, "
            f"technical={factor_score.get('technical', 0.0)}, "
            f"fundamentals={factor_score.get('fundamentals', 0.0)}, "
            f"sentiment={factor_score.get('sentiment', 0.0)}, "
            f"news={factor_score.get('news', 0.0)}, "
            f"alpha={factor_score.get('alpha', 0.0)}"
        )
    if position_sizing:
        lines.append(
            f"- Position sizing: target={position_sizing.get('target_position_size', 0.0)}, "
            f"max={position_sizing.get('max_position_size', 0.0)}, "
            f"stop_loss_buffer={position_sizing.get('stop_loss_buffer', 0.0)}"
        )
    if risk_gate:
        lines.append(
            f"- Risk gate: approved={risk_gate.get('approved', True)}, "
            f"forced_rating={risk_gate.get('forced_rating', '')}, "
            f"capped_size={risk_gate.get('capped_position_size', 0.0)}"
        )
    if execution_plan:
        lines.append(
            f"- Execution: action={execution_plan.get('action', '')}, "
            f"target_position_size={execution_plan.get('target_position_size', 0.0)}"
        )
    if alpha_summary:
        lines.append(
            f"- Alpha experience: registry_entries={alpha_summary.get('registry_entry_count', 0)}, "
            f"avg_alpha={alpha_summary.get('average_realized_alpha', 0.0)}, "
            f"win_rate={alpha_summary.get('positive_alpha_win_rate', 0.0)}, "
            f"selected_sample_count={alpha_summary.get('selected_alpha_sample_count', 0)}"
        )
    if len(lines) == 1:
        lines.append("- unavailable")
    return "\n".join(lines)


_EVIDENCE_KEYWORDS = (
    "risk", "support", "resistance", "trend", "momentum", "volatility",
    "liquidity", "volume", "catalyst", "macro", "inflation", "rate",
    "fed", "etf", "rsi", "macd", "atr", "bollinger", "drawdown",
    "bullish", "bearish", "neutral", "confidence", "signal",
    "风险", "支撑", "阻力", "趋势", "动量", "波动", "流动性",
    "成交", "催化", "宏观", "通胀", "利率", "美联储", "情绪",
    "看涨", "看跌", "中性", "置信", "信号",
)


def _truncate_line(line: str, max_chars: int = 260) -> str:
    line = " ".join(str(line or "").strip().split())
    if len(line) <= max_chars:
        return line
    return line[: max_chars - 3].rstrip() + "..."


def _prioritized_report_lines(report: str) -> list[str]:
    body = re.sub(
        r"FEATURE_SUMMARY[\s\S]*?END_FEATURE_SUMMARY",
        "",
        str(report or ""),
        flags=re.IGNORECASE,
    )
    lines = []
    fallback = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or set(line) <= {"-", "|", ":", " "}:
            continue
        compact = _truncate_line(line)
        fallback.append(compact)
        lower = compact.lower()
        has_number = bool(re.search(r"\d", compact))
        has_keyword = any(keyword in lower for keyword in _EVIDENCE_KEYWORDS)
        is_heading = compact.startswith("#")
        is_table_row = compact.startswith("|")
        if has_number or has_keyword or is_heading or is_table_row:
            lines.append(compact)
    return lines or fallback[:8]


def build_report_evidence_pack(
    state: dict,
    *,
    report_key: str,
    features_key: str,
    label: str,
    max_chars: int = 1600,
) -> str:
    """Return a compact downstream context while preserving full reports in state."""
    report = str(state.get(report_key) or "").strip()
    features = state.get(features_key) or {}
    if not report and not features:
        return f"{label}: unavailable"

    parts = [f"{label} evidence pack:"]
    if isinstance(features, dict) and features:
        parts.append(
            "- Summary: "
            f"score={features.get('score', 'n/a')}, "
            f"confidence={features.get('confidence', 'n/a')}, "
            f"key_signal={features.get('key_signal', 'n/a')}, "
            f"risk_flag={features.get('risk_flag', 'n/a')}"
        )

    remaining = max_chars - sum(len(part) + 1 for part in parts)
    for line in _prioritized_report_lines(report):
        bullet = f"- Evidence: {line}"
        if remaining <= 0:
            break
        if len(bullet) > remaining:
            bullet = bullet[: max(0, remaining - 3)].rstrip() + "..."
        parts.append(bullet)
        remaining -= len(bullet) + 1

    return "\n".join(parts)


def compact_history(history: str, keep_recent_lines: int = 8) -> str:
    """Keep only the most recent non-empty lines from a long debate history."""
    if not history:
        return ""
    lines = [line for line in history.splitlines() if line.strip()]
    if len(lines) <= keep_recent_lines:
        return "\n".join(lines)
    tail = "\n".join(lines[-keep_recent_lines:])
    return f"[Earlier debate omitted for brevity]\n{tail}"

def create_msg_delete(remove_existing: bool = True):
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        if not remove_existing:
            # Parallel analyst branches can all see the same pre-merge message
            # ids. If each branch emits RemoveMessage for those ids, the first
            # branch wins and later branches fail because the ids are gone.
            return {"messages": []}

        messages = state["messages"]

        # Remove all messages
        removal_operations = []
        seen_ids = set()
        for message in messages:
            message_id = getattr(message, "id", None)
            if not message_id or message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            removal_operations.append(RemoveMessage(id=message_id))

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
