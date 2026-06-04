from langchain_core.messages import HumanMessage, RemoveMessage
from tradingagents.core.time_context import TimeContext, coerce_time_context

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
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


def compact_history(history: str, keep_recent_lines: int = 8) -> str:
    """Keep only the most recent non-empty lines from a long debate history."""
    if not history:
        return ""
    lines = [line for line in history.splitlines() if line.strip()]
    if len(lines) <= keep_recent_lines:
        return "\n".join(lines)
    tail = "\n".join(lines[-keep_recent_lines:])
    return f"[Earlier debate omitted for brevity]\n{tail}"

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
