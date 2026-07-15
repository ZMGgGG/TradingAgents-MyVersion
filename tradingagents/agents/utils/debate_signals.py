from __future__ import annotations

from typing import Optional

from tradingagents.agents.schemas import (
    InvestmentDebateSignal,
    InvestmentStance,
    RiskDebateSignal,
    RiskStance,
)


def default_investment_signal(
    stance: InvestmentStance,
    thesis: str,
    agent_name: str,
) -> InvestmentDebateSignal:
    """Create a fallback investment signal when parsing fails."""
    return InvestmentDebateSignal(
        agent_name=agent_name,
        stance=stance,
        score=0.5,
        confidence=0.5,
        evidence_quality=0.4,
        time_horizon_days=5,
        thesis=thesis.strip() or f"{agent_name} produced an unstructured view.",
        rebuttal="Fallback path used because structured output was unavailable.",
        key_risks="Signal confidence is limited because no structured evidence was returned.",
        evidence=[],
    )


def default_risk_signal(
    stance: RiskStance,
    thesis: str,
    agent_name: str,
) -> RiskDebateSignal:
    """Create a fallback risk signal when parsing fails."""
    return RiskDebateSignal(
        agent_name=agent_name,
        stance=stance,
        score=0.5,
        confidence=0.5,
        evidence_quality=0.4,
        time_horizon_days=5,
        thesis=thesis.strip() or f"{agent_name} produced an unstructured risk view.",
        guardrails="Fallback path used because structured output was unavailable.",
        evidence=[],
    )


def summarize_investment_signals(
    bull_signal: Optional[InvestmentDebateSignal],
    bear_signal: Optional[InvestmentDebateSignal],
) -> dict[str, float | str]:
    """Aggregate the bull and bear debate into a verifiable summary."""
    signals = [s for s in (bull_signal, bear_signal) if s is not None]
    if not signals:
        return {
            "summary": "No structured investment debate signals were captured.",
            "net_score": 0.0,
            "average_confidence": 0.0,
            "recommended_rating": "Hold",
        }

    weighted_scores = []
    for signal in signals:
        direction = 1.0 if signal.stance == InvestmentStance.BULLISH else -1.0
        weighted_scores.append(direction * signal.score * signal.confidence * signal.evidence_quality)

    net_score = sum(weighted_scores) / len(weighted_scores)
    average_confidence = sum(s.confidence for s in signals) / len(signals)
    if net_score >= 0.1:
        recommendation = "Buy"
    elif net_score <= -0.1:
        recommendation = "Sell"
    else:
        recommendation = "Hold"

    summary = (
        f"Investment debate summary: net_score={net_score:.3f}, "
        f"average_confidence={average_confidence:.3f}, "
        f"recommendation={recommendation}."
    )
    return {
        "summary": summary,
        "net_score": round(net_score, 4),
        "average_confidence": round(average_confidence, 4),
        "recommended_rating": recommendation,
    }


def summarize_risk_signals(
    aggressive_signal: Optional[RiskDebateSignal],
    conservative_signal: Optional[RiskDebateSignal],
    neutral_signal: Optional[RiskDebateSignal],
) -> dict[str, float | str]:
    """Aggregate the risk debate into a verifiable summary."""
    signals = [s for s in (aggressive_signal, conservative_signal, neutral_signal) if s is not None]
    if not signals:
        return {
            "summary": "No structured risk debate signals were captured.",
            "net_score": 0.0,
            "average_confidence": 0.0,
            "recommended_posture": "Balanced",
        }

    stance_weights = {
        RiskStance.AGGRESSIVE: 1.0,
        RiskStance.NEUTRAL: 0.0,
        RiskStance.CONSERVATIVE: -1.0,
    }
    weighted_scores = [
        stance_weights[s.stance] * s.score * s.confidence * s.evidence_quality
        for s in signals
    ]
    net_score = sum(weighted_scores) / len(weighted_scores)
    average_confidence = sum(s.confidence for s in signals) / len(signals)
    if net_score >= 0.1:
        posture = "Aggressive"
    elif net_score <= -0.1:
        posture = "Conservative"
    else:
        posture = "Balanced"

    summary = (
        f"Risk debate summary: net_score={net_score:.3f}, "
        f"average_confidence={average_confidence:.3f}, "
        f"posture={posture}."
    )
    return {
        "summary": summary,
        "net_score": round(net_score, 4),
        "average_confidence": round(average_confidence, 4),
        "recommended_posture": posture,
    }
