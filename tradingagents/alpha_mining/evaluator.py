from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schemas import AlphaCandidate, AlphaMiningResult


@dataclass(frozen=True)
class AlphaEvaluation:
    """Compact validation result for a mined alpha candidate."""

    candidate_name: str
    passed: bool
    score: float
    notes: list[str]
    realized_return: float = 0.0
    realized_alpha: float = 0.0


class AlphaEvaluator:
    """Evaluate mined alpha candidates against simple deterministic gates."""

    def __init__(
        self,
        min_confidence: float = 0.45,
        min_stability: float = 0.45,
        min_absolute_signal: float = 0.08,
        max_redundancy_penalty: float = 0.30,
    ):
        self.min_confidence = min_confidence
        self.min_stability = min_stability
        self.min_absolute_signal = min_absolute_signal
        self.max_redundancy_penalty = max_redundancy_penalty

    def evaluate(self, result: AlphaMiningResult | dict[str, Any]) -> AlphaEvaluation:
        payload = result.model_dump() if isinstance(result, AlphaMiningResult) else dict(result)
        candidate = self._candidate_from_payload(payload)
        notes: list[str] = []

        passed = True
        if abs(candidate.signal_score) < self.min_absolute_signal:
            passed = False
            notes.append("signal_too_weak")
        if candidate.confidence < self.min_confidence:
            passed = False
            notes.append("confidence_too_low")

        stability = float(payload.get("stability", 0.0))
        if stability < self.min_stability:
            passed = False
            notes.append("stability_too_low")

        redundancy_penalty = float(payload.get("redundancy_penalty", 0.0))
        if redundancy_penalty > self.max_redundancy_penalty:
            passed = False
            notes.append("redundancy_too_high")

        realized_return = float(payload.get("realized_return", 0.0))
        realized_alpha = float(payload.get("realized_alpha", 0.0))
        if realized_alpha < -0.02:
            passed = False
            notes.append("negative_realized_alpha")

        structural_score = abs(candidate.signal_score) * candidate.confidence * max(0.0, stability)
        performance_bonus = max(0.0, realized_return) * 0.5 + max(0.0, realized_alpha) * 0.5
        score = max(0.0, min(1.0, structural_score + performance_bonus))
        return AlphaEvaluation(
            candidate_name=candidate.name,
            passed=passed,
            score=score,
            notes=notes,
            realized_return=realized_return,
            realized_alpha=realized_alpha,
        )

    def _candidate_from_payload(self, payload: dict[str, Any]) -> AlphaCandidate:
        selected = payload.get("selected_alpha", {}) or {}
        return AlphaCandidate(
            name=str(selected.get("name", "unknown_alpha")),
            hypothesis=str(selected.get("hypothesis", "")),
            expression=str(selected.get("expression", "")),
            signal_score=float(selected.get("signal_score", payload.get("signal_score", 0.0))),
            confidence=float(selected.get("confidence", payload.get("confidence", 0.0))),
            complexity=int(selected.get("complexity", 1)),
            validation_status=str(selected.get("validation_status", "unknown")),
            evidence=list(selected.get("evidence", [])),
        )
