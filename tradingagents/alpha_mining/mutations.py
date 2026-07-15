from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .schemas import AlphaCandidate


@dataclass(frozen=True)
class AlphaMutation:
    name_suffix: str
    hypothesis_suffix: str
    expression_suffix: str
    score_delta: float = 0.0
    confidence_delta: float = 0.0


def mutate_candidate(candidate: AlphaCandidate, mutation: AlphaMutation) -> AlphaCandidate:
    """Create a slightly perturbed candidate for trajectory-style refinement."""
    return AlphaCandidate(
        name=f"{candidate.name}_{mutation.name_suffix}",
        hypothesis=f"{candidate.hypothesis} {mutation.hypothesis_suffix}".strip(),
        expression=f"{candidate.expression} {mutation.expression_suffix}".strip(),
        signal_score=max(-1.0, min(1.0, candidate.signal_score + mutation.score_delta)),
        confidence=max(0.0, min(1.0, candidate.confidence + mutation.confidence_delta)),
        complexity=candidate.complexity + 1,
        validation_status="mutated_proxy",
        evidence=list(candidate.evidence),
    )


def crossover_candidates(left: AlphaCandidate, right: AlphaCandidate, name: str = "crossover") -> AlphaCandidate:
    """Blend two candidates into a hybrid candidate."""
    return AlphaCandidate(
        name=f"{left.name}_{right.name}_{name}",
        hypothesis=f"{left.hypothesis} Combined with: {right.hypothesis}",
        expression=f"({left.expression}) + ({right.expression})",
        signal_score=max(-1.0, min(1.0, (left.signal_score + right.signal_score) / 2.0)),
        confidence=max(0.0, min(1.0, (left.confidence + right.confidence) / 2.0)),
        complexity=max(left.complexity, right.complexity) + 1,
        validation_status="crossover_proxy",
        evidence=list(dict.fromkeys([*left.evidence, *right.evidence])),
    )


def generate_mutation_set(candidate: AlphaCandidate) -> list[AlphaCandidate]:
    """Return a small deterministic mutation set for the given candidate."""
    mutations = [
        AlphaMutation("trend_boost", "with stronger trend confirmation.", "-> stronger trend filter", score_delta=0.06, confidence_delta=0.03),
        AlphaMutation("risk_discount", "with tighter risk discounting.", "-> heavier risk discount", score_delta=-0.04, confidence_delta=0.02),
        AlphaMutation("quality_focus", "with quality emphasis.", "-> quality-weighted variant", score_delta=0.02, confidence_delta=0.05),
    ]
    return [mutate_candidate(candidate, mutation) for mutation in mutations]


def generate_crossover_set(candidates: Iterable[AlphaCandidate]) -> list[AlphaCandidate]:
    items = list(candidates)
    if len(items) < 2:
        return []
    hybrids: list[AlphaCandidate] = []
    for index in range(len(items) - 1):
        hybrids.append(crossover_candidates(items[index], items[index + 1], name=f"blend{index + 1}"))
    return hybrids
