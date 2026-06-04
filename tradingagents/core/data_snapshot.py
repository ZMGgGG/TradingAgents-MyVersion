from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .time_context import TimeContext, coerce_time_context


def _snapshot_time() -> str:
    """Return the current UTC timestamp for snapshots."""
    return datetime.now(timezone.utc).isoformat()


class DataSnapshot(BaseModel):
    snapshot_id: str
    ticker: str
    asset_type: str = "stock"
    trade_date: str
    time_context: TimeContext
    reports: dict[str, str] = Field(default_factory=dict)
    investment_signal_summary: str = ""
    risk_signal_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at_utc: str = Field(default_factory=_snapshot_time)

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DataSnapshot":
        """Build a reproducible snapshot from the final agent state."""
        trade_date = str(state.get("trade_date", ""))
        time_context = coerce_time_context(state.get("time_context"), trade_date)
        ticker = str(state.get("company_of_interest", ""))
        reports = {
            "market_report": str(state.get("market_report", "")),
            "sentiment_report": str(state.get("sentiment_report", "")),
            "news_report": str(state.get("news_report", "")),
            "fundamentals_report": str(state.get("fundamentals_report", "")),
            "investment_plan": str(state.get("investment_plan", "")),
            "trader_investment_plan": str(state.get("trader_investment_plan", "")),
            "final_trade_decision": str(state.get("final_trade_decision", "")),
        }
        metadata = {
            "investment_signal_score": state.get("investment_debate_state", {}).get("signal_score", 0.0),
            "investment_signal_confidence": state.get("investment_debate_state", {}).get("signal_confidence", 0.0),
            "risk_signal_score": state.get("risk_debate_state", {}).get("signal_score", 0.0),
            "risk_signal_confidence": state.get("risk_debate_state", {}).get("signal_confidence", 0.0),
        }
        return cls(
            snapshot_id=f"{ticker}:{time_context.as_of_date}",
            ticker=ticker,
            asset_type=str(state.get("asset_type", "stock")),
            trade_date=trade_date,
            time_context=time_context,
            reports=reports,
            investment_signal_summary=str(
                state.get("investment_debate_state", {}).get("signal_summary", "")
            ),
            risk_signal_summary=str(
                state.get("risk_debate_state", {}).get("signal_summary", "")
            ),
            metadata=metadata,
        )

    def to_log_payload(self) -> dict[str, Any]:
        """Serialize the snapshot for JSON logs."""
        return self.model_dump()
