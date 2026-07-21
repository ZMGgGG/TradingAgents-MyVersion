from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConclusionEvent(BaseModel):
    event_type: str
    note: str = ""
    created_at: str = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConclusionTrack(BaseModel):
    conclusion_id: str
    source_run_id: str = ""
    ticker: str
    asset_type: str = "stock"
    thesis: str = ""
    rating: str = ""
    action: str = "hold"
    target_position_size: float = 0.0
    status: str = "tracking"
    analysis_date: str = ""
    opened_at: str = Field(default_factory=utc_now)
    horizon_days: int = 20
    entry_price: float | None = None
    current_price: float | None = None
    benchmark_return: float | None = None
    raw_return: float | None = None
    alpha_return: float | None = None
    factor_score: dict[str, Any] = Field(default_factory=dict)
    risk_gate_result: dict[str, Any] = Field(default_factory=dict)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    simulation_links: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    review_notes: str = ""
    events: list[ConclusionEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def with_lifecycle_status(self, now: datetime | None = None) -> "ConclusionTrack":
        if self.status not in {"tracking", "due_review"}:
            return self
        age_days = self.age_days(now)
        if age_days >= max(1, int(self.horizon_days or 1)):
            clone = self.model_copy()
            clone.status = "due_review"
            return clone
        return self

    def age_days(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        try:
            opened = datetime.fromisoformat(str(self.opened_at).replace("Z", "+00:00"))
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
        except ValueError:
            return 0
        return max(0, (now - opened).days)

    def progress(self, now: datetime | None = None) -> float:
        horizon = max(1, int(self.horizon_days or 1))
        return min(1.0, self.age_days(now) / horizon)

    def current_return(self) -> float | None:
        if self.raw_return is not None:
            return self.raw_return
        if self.entry_price and self.current_price:
            return (self.current_price / self.entry_price) - 1.0
        return None

    def public_payload(self, now: datetime | None = None) -> dict[str, Any]:
        track = self.with_lifecycle_status(now)
        payload = track.model_dump()
        payload["age_days"] = track.age_days(now)
        payload["progress"] = track.progress(now)
        payload["current_return"] = track.current_return()
        return payload


class ConclusionBook(BaseModel):
    tracks: list[ConclusionTrack] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now)
