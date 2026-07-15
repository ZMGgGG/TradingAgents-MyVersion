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
        asset_type = str(state.get("asset_type", "stock")).lower()
        confidence = float(state.get("investment_debate_state", {}).get("signal_confidence", 0.0))
        factor_score = float(state.get("factor_score", {}).get("composite_score", 0.0))
        risk_score = float(state.get("risk_debate_state", {}).get("signal_score", 0.0))
        proposed_size = float(state.get("position_sizing", {}).get("target_position_size", 0.0))
        crypto_quality_cap: float | None = None

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

        if asset_type == "crypto":
            market_ledger = state.get("market_evidence_ledger", {}) or {}
            sentiment_ledger = state.get("sentiment_evidence_ledger", {}) or {}
            news_ledger = state.get("news_evidence_ledger", {}) or {}
            market_flags = set(market_ledger.get("data_quality_flags", []) or [])
            sentiment_coverage = float(sentiment_ledger.get("source_coverage", 0.0) or 0.0)
            news_diversity = int(news_ledger.get("source_diversity", 0) or 0)
            news_count = int(news_ledger.get("source_count", 0) or 0)
            derivatives_missing = (
                "crypto_derivatives_unavailable" in market_flags
                or "derivatives_data_unavailable" in market_flags
            )
            if derivatives_missing:
                crypto_quality_cap = 0.04
                reasons.append("crypto derivatives positioning data unavailable; position size capped at 4%")
            if derivatives_missing and sentiment_coverage < 0.5 and (news_diversity <= 1 or news_count <= 1):
                approved = False
                forced_rating = "Hold"
                reasons.append(
                    "crypto evidence coverage is too thin: derivatives unavailable, sentiment coverage below 50%, and news source diversity <= 1"
                )

        capped_size = min(proposed_size, self.max_position_size)
        if crypto_quality_cap is not None:
            capped_size = min(capped_size, crypto_quality_cap)
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
