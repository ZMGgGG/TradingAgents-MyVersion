from __future__ import annotations

from pydantic import BaseModel


class PositionSizingPlan(BaseModel):
    target_position_size: float
    max_position_size: float
    stop_loss_buffer: float
    sizing_summary: str


class PositionSizer:
    """Translate factor strength and confidence into a baseline position size."""

    def __init__(self, base_size: float = 0.04, max_size: float = 0.12):
        self.base_size = base_size
        self.max_size = max_size

    def size(self, state: dict) -> PositionSizingPlan:
        """Produce a baseline position sizing plan from factor and confidence inputs."""
        confidence = float(state.get("investment_debate_state", {}).get("signal_confidence", 0.0))
        factor_score = float(state.get("factor_score", {}).get("composite_score", 0.0))
        risk_score = float(state.get("risk_debate_state", {}).get("signal_score", 0.0))

        conviction = max(0.0, factor_score) * max(0.0, confidence)
        risk_discount = max(0.4, 1.0 - max(0.0, -risk_score))
        target_size = min(self.max_size, self.base_size + conviction * 0.10) * risk_discount
        stop_loss_buffer = 0.05 + max(0.0, -risk_score) * 0.05
        summary = (
            f"Position sizing target={target_size:.2%}, max={self.max_size:.2%}, "
            f"stop_loss_buffer={stop_loss_buffer:.2%}."
        )
        return PositionSizingPlan(
            target_position_size=target_size,
            max_position_size=self.max_size,
            stop_loss_buffer=stop_loss_buffer,
            sizing_summary=summary,
        )
