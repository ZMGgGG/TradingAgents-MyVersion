from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class TimeContext(BaseModel):
    trade_date: str
    as_of_date: str
    timezone: str = "America/New_York"
    market_session: str = "close"
    analysis_lookback_days: int = 30
    created_at_utc: str = Field(default_factory=_utc_now_iso)

    @classmethod
    def from_trade_date(
        cls,
        trade_date: str,
        timezone_name: str = "America/New_York",
        market_session: str = "close",
        as_of_date: Optional[str] = None,
        analysis_lookback_days: int = 30,
    ) -> "TimeContext":
        """Build a time context from a trading date."""
        resolved_date = as_of_date or str(trade_date)
        return cls(
            trade_date=str(trade_date),
            as_of_date=resolved_date,
            timezone=timezone_name,
            market_session=market_session,
            analysis_lookback_days=analysis_lookback_days,
        )

    def news_start_date(self, lookback_days: Optional[int] = None) -> str:
        """Return the start date for a backward-looking news window."""
        lookback_days = lookback_days or self.analysis_lookback_days
        start = datetime.strptime(self.as_of_date, "%Y-%m-%d") - timedelta(days=lookback_days)
        return start.strftime("%Y-%m-%d")

    def price_start_date(self, lookback_days: Optional[int] = None) -> str:
        """Return the start date for a backward-looking price window."""
        lookback_days = lookback_days or self.analysis_lookback_days
        start = datetime.strptime(self.as_of_date, "%Y-%m-%d") - timedelta(days=lookback_days)
        return start.strftime("%Y-%m-%d")

    def to_prompt_string(self) -> str:
        """Render the time rules for agent prompts."""
        return (
            f"Use only information that would have been available by {self.as_of_date} "
            f"({self.market_session}, {self.timezone}). Do not assume access to later data."
        )


def coerce_time_context(
    value: Any,
    trade_date: str,
    timezone_name: str = "America/New_York",
    market_session: str = "close",
) -> TimeContext:
    """Normalize an arbitrary object into a TimeContext."""
    if isinstance(value, TimeContext):
        return value
    if isinstance(value, Mapping) and value:
        return TimeContext.model_validate(value)
    return TimeContext.from_trade_date(
        trade_date=str(trade_date),
        timezone_name=timezone_name,
        market_session=market_session,
        analysis_lookback_days=30,
    )
