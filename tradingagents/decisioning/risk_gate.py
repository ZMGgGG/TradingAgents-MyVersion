from __future__ import annotations

from pydantic import BaseModel


class RiskGateResult(BaseModel):
    approved: bool
    forced_rating: str
    reasons: list[str]
    capped_position_size: float


class RiskGate:
    """Apply deterministic hard risk rules before final portfolio approval."""

    def __init__(
        self,
        min_confidence: float = 0.55,
        min_factor_score: float = -0.05,
        max_position_size: float = 0.12,
    ):
        self.min_confidence = min_confidence
        self.min_factor_score = min_factor_score
        self.max_position_size = max_position_size

    def evaluate(self, state: dict) -> RiskGateResult:
        """Apply hard gating rules to the current decision state."""
        reasons: list[str] = []
        confidence = float(state.get("investment_debate_state", {}).get("signal_confidence", 0.0))
        factor_score = float(state.get("factor_score", {}).get("composite_score", 0.0))
        risk_score = float(state.get("risk_debate_state", {}).get("signal_score", 0.0))
        proposed_size = float(state.get("position_sizing", {}).get("target_position_size", 0.0))

        approved = True
        forced_rating = ""

        if confidence < self.min_confidence:
            approved = False
            forced_rating = "Hold"
            reasons.append(
                f"confidence {confidence:.2f} is below threshold {self.min_confidence:.2f}"
            )
        if factor_score < self.min_factor_score:
            approved = False
            forced_rating = "Hold"
            reasons.append(
                f"factor score {factor_score:.2f} is below threshold {self.min_factor_score:.2f}"
            )
        if risk_score <= -0.35:
            approved = False
            forced_rating = "Hold"
            reasons.append(
                f"risk score {risk_score:.2f} indicates elevated downside risk"
            )

        capped_size = min(proposed_size, self.max_position_size)
        if capped_size < proposed_size:
            reasons.append(
                f"position size capped from {proposed_size:.2%} to {capped_size:.2%}"
            )

        return RiskGateResult(
            approved=approved,
            forced_rating=forced_rating,
            reasons=reasons,
            capped_position_size=capped_size,
        )
