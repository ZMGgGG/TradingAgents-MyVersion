"""Pydantic schemas used by agents that produce structured output.

The framework's primary artifact is still prose: each agent's natural-language
reasoning is what users read in the saved markdown reports and what the
downstream agents read as context.  Structured output is layered onto the
three decision-making agents (Research Manager, Trader, Portfolio Manager)
so that:

- Their outputs follow consistent section headers across runs and providers
- Each provider's native structured-output mode is used (json_schema for
  OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic)
- Schema field descriptions become the model's output instructions, freeing
  the prompt body to focus on context and the rating-scale guidance
- A render helper turns the parsed Pydantic instance back into the same
  markdown shape the rest of the system already consumes, so display,
  memory log, and saved reports keep working unchanged
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared rating types
# ---------------------------------------------------------------------------


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader.

    The Trader's job is to translate the Research Manager's investment plan
    into a concrete transaction proposal: should the desk execute a Buy, a
    Sell, or sit on Hold this round.  Position sizing and the nuanced
    Overweight / Underweight calls happen later at the Portfolio Manager.
    """

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


class InvestmentStance(str, Enum):
    """Directional stance for the bull/bear debate."""

    BULLISH = "Bullish"
    BEARISH = "Bearish"


class RiskStance(str, Enum):
    """Directional stance for the risk debate."""

    AGGRESSIVE = "Aggressive"
    NEUTRAL = "Neutral"
    CONSERVATIVE = "Conservative"


class EvidenceItem(BaseModel):
    """Single evidence point attached to a structured debate signal."""

    source: str = Field(description="The source category, such as technicals or news.")
    claim: str = Field(description="The evidence-backed claim from that source.")
    strength: float = Field(
        ge=0.0,
        le=1.0,
        description="A normalized evidence strength score between 0 and 1.",
    )


class AnalystFeatureSummary(BaseModel):
    score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Normalized directional score in the range [-1, 1].",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the feature summary.",
    )
    key_signal: str = Field(
        description="Primary signal or regime takeaway.",
    )
    risk_flag: str = Field(
        description="Primary risk caveat or degradation flag.",
    )


class InvestmentDebateSignal(BaseModel):
    """Structured signal produced by the bull and bear researchers."""

    agent_name: str = Field(description="The name of the agent producing this signal.")
    stance: InvestmentStance = Field(description="The directional stance for this argument.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="The strength of the directional thesis on a 0-1 scale.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the stance based on available data.",
    )
    evidence_quality: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality of evidence behind the argument on a 0-1 scale.",
    )
    time_horizon_days: int = Field(
        ge=1,
        description="The intended holding horizon for this thesis in days.",
    )
    thesis: str = Field(description="The main investment thesis in plain language.")
    rebuttal: str = Field(description="The key rebuttal to the opposing side.")
    key_risks: str = Field(description="The main risks that could invalidate this stance.")
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence items that support the thesis.",
    )


class RiskDebateSignal(BaseModel):
    """Structured signal produced by the risk analysts."""

    agent_name: str = Field(description="The name of the agent producing this signal.")
    stance: RiskStance = Field(description="The risk posture represented by this argument.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="The intensity of the stance on a 0-1 scale.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the risk view based on available data.",
    )
    evidence_quality: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality of the evidence used by this risk view.",
    )
    time_horizon_days: int = Field(
        ge=1,
        description="The risk horizon for this view in days.",
    )
    thesis: str = Field(description="The main risk argument in plain language.")
    guardrails: str = Field(description="Operational guardrails suggested by this stance.")
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence items that support the risk thesis.",
    )


# ---------------------------------------------------------------------------
# Research Manager
# ---------------------------------------------------------------------------


class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager.

    Hand-off to the Trader: the recommendation pins the directional view,
    the rationale captures which side of the bull/bear debate carried the
    argument, and the strategic actions translate that into concrete
    instructions the trader can execute against.
    """

    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Reserve Hold for situations where the "
            "evidence on both sides is genuinely balanced; otherwise commit to "
            "the side with the stronger arguments."
        ),
    )
    rationale: str = Field(
        description=(
            "Conversational summary of the key points from both sides of the "
            "debate, ending with which arguments led to the recommendation. "
            "Speak naturally, as if to a teammate."
        ),
    )
    strategic_actions: str = Field(
        description=(
            "Concrete steps for the trader to implement the recommendation, "
            "including position sizing guidance consistent with the rating."
        ),
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown for storage and the trader's prompt context."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


def _render_evidence_lines(evidence: list[EvidenceItem]) -> str:
    """Render evidence items into a compact markdown block."""
    if not evidence:
        return "- No structured evidence captured."
    return "\n".join(
        f"- {item.source}: {item.claim} (strength={item.strength:.2f})"
        for item in evidence
    )


def render_investment_debate_signal(signal: InvestmentDebateSignal) -> str:
    """Render a structured bull/bear signal to markdown."""
    return "\n".join([
        f"**Stance**: {signal.stance.value}",
        f"**Score**: {signal.score:.2f}",
        f"**Confidence**: {signal.confidence:.2f}",
        f"**Evidence Quality**: {signal.evidence_quality:.2f}",
        f"**Time Horizon (Days)**: {signal.time_horizon_days}",
        f"**Thesis**: {signal.thesis}",
        f"**Rebuttal**: {signal.rebuttal}",
        f"**Key Risks**: {signal.key_risks}",
        "**Evidence**:",
        _render_evidence_lines(signal.evidence),
    ])


def render_risk_debate_signal(signal: RiskDebateSignal) -> str:
    """Render a structured risk signal to markdown."""
    return "\n".join([
        f"**Stance**: {signal.stance.value}",
        f"**Score**: {signal.score:.2f}",
        f"**Confidence**: {signal.confidence:.2f}",
        f"**Evidence Quality**: {signal.evidence_quality:.2f}",
        f"**Time Horizon (Days)**: {signal.time_horizon_days}",
        f"**Thesis**: {signal.thesis}",
        f"**Guardrails**: {signal.guardrails}",
        "**Evidence**:",
        _render_evidence_lines(signal.evidence),
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader.

    The trader reads the Research Manager's investment plan and the analyst
    reports, then turns them into a concrete transaction: what action to
    take, the reasoning that justifies it, and the practical levels for
    entry, stop-loss, and sizing.
    """

    action: TraderAction = Field(
        description="The transaction direction. Exactly one of Buy / Hold / Sell.",
    )
    reasoning: str = Field(
        description=(
            "The case for this action, anchored in the analysts' reports and "
            "the research plan. Two to four sentences."
        ),
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Optional entry price target in the instrument's quote currency.",
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Optional stop-loss price in the instrument's quote currency.",
    )
    position_sizing: Optional[str] = Field(
        default=None,
        description="Optional sizing guidance, e.g. '5% of portfolio'.",
    )


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown.

    The trailing ``FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`` line is
    preserved for backward compatibility with the analyst stop-signal text
    and any external code that greps for it.
    """
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Structured output produced by the Portfolio Manager.

    The model fills every field as part of its primary LLM call; no separate
    extraction pass is required. Field descriptions double as the model's
    output instructions, so the prompt body only needs to convey context and
    the rating-scale guidance.
    """

    rating: PortfolioRating = Field(
        description=(
            "The final position rating. Exactly one of Buy / Overweight / Hold / "
            "Underweight / Sell, picked based on the analysts' debate."
        ),
    )
    executive_summary: str = Field(
        description=(
            "A concise action plan covering entry strategy, position sizing, "
            "key risk levels, and time horizon. Two to four sentences."
        ),
    )
    investment_thesis: str = Field(
        description=(
            "Detailed reasoning anchored in specific evidence from the analysts' "
            "debate. If prior lessons are referenced in the prompt context, "
            "incorporate them; otherwise rely solely on the current analysis."
        ),
    )
    price_target: Optional[float] = Field(
        default=None,
        description="Optional target price in the instrument's quote currency.",
    )
    time_horizon: Optional[str] = Field(
        default=None,
        description="Optional recommended holding period, e.g. '3-6 months'.",
    )
    target_position_size: Optional[float] = Field(
        default=None,
        description="Optional target portfolio weight as a decimal, e.g. 0.05 for 5%.",
    )
    risk_gate_status: Optional[str] = Field(
        default=None,
        description="Optional note describing whether the deterministic risk gate approved the trade.",
    )


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision back to the markdown shape the rest of the system expects.

    Memory log, CLI display, and saved report files all read this markdown,
    so the rendered output preserves the exact section headers (``**Rating**``,
    ``**Executive Summary**``, ``**Investment Thesis**``) that downstream
    parsers and the report writers already handle.
    """
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    if decision.target_position_size is not None:
        parts.extend(["", f"**Target Position Size**: {decision.target_position_size:.2%}"])
    if decision.risk_gate_status:
        parts.extend(["", f"**Risk Gate Status**: {decision.risk_gate_status}"])
    return "\n".join(parts)


def _extract_markdown_field(text: str, label: str) -> Optional[str]:
    pattern = rf"\*\*{re.escape(label)}\*\*:\s*(.+?)(?=\n\*\*|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_plain_field(text: str, label: str) -> Optional[str]:
    pattern = rf"^{re.escape(label)}:\s*(.+?)(?=^[A-Z_ ]+:\s|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_field(text: str, *labels: str) -> Optional[str]:
    for label in labels:
        value = _extract_markdown_field(text, label)
        if value:
            return value
        value = _extract_plain_field(text, label)
        if value:
            return value
    return None


def _extract_summary_block(text: str) -> str:
    match = re.search(
        r"STRUCTURED_SUMMARY\s*(.*?)\s*END_STRUCTURED_SUMMARY",
        text,
        flags=re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return text


def _parse_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None


def _parse_signed_float(value: Optional[str], default: float = 0.0) -> float:
    parsed = _parse_float(value)
    if parsed is None:
        return default
    raw = (value or "").strip()
    if raw.startswith("-"):
        parsed = -abs(parsed)
    return parsed


def _parse_int(value: Optional[str], default: int) -> int:
    parsed = _parse_float(value)
    return int(parsed) if parsed is not None else default


def _parse_investment_stance(value: Optional[str], default: InvestmentStance) -> InvestmentStance:
    normalized = (value or "").strip().lower()
    if normalized.startswith("bear"):
        return InvestmentStance.BEARISH
    if normalized.startswith("bull"):
        return InvestmentStance.BULLISH
    return default


def _parse_risk_stance(value: Optional[str], default: RiskStance) -> RiskStance:
    normalized = (value or "").strip().lower()
    if normalized.startswith("agg"):
        return RiskStance.AGGRESSIVE
    if normalized.startswith("cons"):
        return RiskStance.CONSERVATIVE
    if normalized.startswith("neu") or normalized.startswith("bal"):
        return RiskStance.NEUTRAL
    return default


def _parse_rating(value: Optional[str], default: PortfolioRating) -> PortfolioRating:
    normalized = (value or "").strip().lower()
    for item in PortfolioRating:
        if item.value.lower() == normalized:
            return item
    return default


def _parse_action(value: Optional[str], default: TraderAction) -> TraderAction:
    normalized = (value or "").strip().lower()
    for item in TraderAction:
        if item.value.lower() == normalized:
            return item
    return default


def parse_investment_debate_signal(
    text: str,
    agent_name: str,
    default_stance: InvestmentStance,
) -> InvestmentDebateSignal:
    summary_text = _extract_summary_block(text)
    return InvestmentDebateSignal(
        agent_name=agent_name,
        stance=_parse_investment_stance(_extract_field(summary_text, "Stance", "STANCE"), default_stance),
        score=_parse_float(_extract_field(summary_text, "Score", "SCORE")) or 0.5,
        confidence=_parse_float(_extract_field(summary_text, "Confidence", "CONFIDENCE")) or 0.5,
        evidence_quality=_parse_float(_extract_field(summary_text, "Evidence Quality", "EVIDENCE_QUALITY")) or 0.4,
        time_horizon_days=_parse_int(_extract_field(summary_text, "Time Horizon (Days)", "TIME_HORIZON_DAYS"), 5),
        thesis=_extract_field(summary_text, "Thesis", "THESIS") or text.strip(),
        rebuttal=_extract_field(summary_text, "Rebuttal", "REBUTTAL") or "Free-text fallback parse.",
        key_risks=_extract_field(summary_text, "Key Risks", "KEY_RISKS") or "Free-text fallback parse.",
        evidence=[],
    )


def parse_risk_debate_signal(
    text: str,
    agent_name: str,
    default_stance: RiskStance,
) -> RiskDebateSignal:
    summary_text = _extract_summary_block(text)
    return RiskDebateSignal(
        agent_name=agent_name,
        stance=_parse_risk_stance(_extract_field(summary_text, "Stance", "STANCE"), default_stance),
        score=_parse_float(_extract_field(summary_text, "Score", "SCORE")) or 0.5,
        confidence=_parse_float(_extract_field(summary_text, "Confidence", "CONFIDENCE")) or 0.5,
        evidence_quality=_parse_float(_extract_field(summary_text, "Evidence Quality", "EVIDENCE_QUALITY")) or 0.4,
        time_horizon_days=_parse_int(_extract_field(summary_text, "Time Horizon (Days)", "TIME_HORIZON_DAYS"), 5),
        thesis=_extract_field(summary_text, "Thesis", "THESIS") or text.strip(),
        guardrails=_extract_field(summary_text, "Guardrails", "GUARDRAILS") or "Free-text fallback parse.",
        evidence=[],
    )


def parse_research_plan(text: str) -> ResearchPlan:
    return ResearchPlan(
        recommendation=_parse_rating(
            _extract_field(text, "Recommendation", "RECOMMENDATION"),
            PortfolioRating.HOLD,
        ),
        rationale=_extract_field(text, "Rationale", "RATIONALE") or text.strip(),
        strategic_actions=_extract_field(text, "Strategic Actions", "STRATEGIC_ACTIONS") or "Maintain discipline and reassess with new data.",
    )


def parse_trader_proposal(text: str) -> TraderProposal:
    return TraderProposal(
        action=_parse_action(_extract_field(text, "Action", "ACTION"), TraderAction.HOLD),
        reasoning=_extract_field(text, "Reasoning", "REASONING") or text.strip(),
        entry_price=_parse_float(_extract_field(text, "Entry Price", "ENTRY_PRICE")),
        stop_loss=_parse_float(_extract_field(text, "Stop Loss", "STOP_LOSS")),
        position_sizing=_extract_field(text, "Position Sizing", "POSITION_SIZING"),
    )


def parse_pm_decision(text: str) -> PortfolioDecision:
    return PortfolioDecision(
        rating=_parse_rating(_extract_field(text, "Rating", "RATING"), PortfolioRating.HOLD),
        executive_summary=_extract_field(text, "Executive Summary", "EXECUTIVE_SUMMARY") or text.strip(),
        investment_thesis=_extract_field(text, "Investment Thesis", "INVESTMENT_THESIS") or text.strip(),
        price_target=_parse_float(_extract_field(text, "Price Target", "PRICE_TARGET")),
        time_horizon=_extract_field(text, "Time Horizon", "TIME_HORIZON"),
        target_position_size=_parse_float(_extract_field(text, "Target Position Size", "TARGET_POSITION_SIZE")),
        risk_gate_status=_extract_field(text, "Risk Gate Status", "RISK_GATE_STATUS"),
    )


def parse_analyst_feature_summary(text: str) -> AnalystFeatureSummary:
    summary_text = _extract_summary_block(text)
    score = _parse_signed_float(_extract_field(summary_text, "Score", "SCORE"), 0.0)
    confidence = _parse_float(_extract_field(summary_text, "Confidence", "CONFIDENCE")) or 0.5
    key_signal = _extract_field(summary_text, "Key Signal", "KEY_SIGNAL") or "No structured key signal captured."
    risk_flag = _extract_field(summary_text, "Risk Flag", "RISK_FLAG") or "No structured risk flag captured."
    return AnalystFeatureSummary(
        score=max(-1.0, min(1.0, score)),
        confidence=max(0.0, min(1.0, confidence)),
        key_signal=key_signal,
        risk_flag=risk_flag,
    )
