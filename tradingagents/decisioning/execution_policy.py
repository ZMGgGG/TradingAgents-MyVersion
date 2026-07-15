from __future__ import annotations


def rating_to_execution_action(rating_text: str) -> str:
    normalized = str(rating_text).strip().lower()
    if normalized in {"buy", "overweight", "hold", "underweight", "sell"}:
        return normalized
    return "hold"


def normalize_target_position_size(action: str, target_position_size: float) -> float:
    size = max(0.0, min(1.0, float(target_position_size)))
    if action == "hold":
        return 0.0
    if action == "underweight":
        return size * 0.5
    return size


def candidate_signal_to_execution(signal_score: float, confidence: float) -> tuple[str, float]:
    """Map a directional signal into a normalized execution action and size."""
    if signal_score > 0.30:
        return "overweight", min(0.12, max(0.04, abs(signal_score) * max(confidence, 0.4)))
    if signal_score > 0.05:
        return "buy", min(0.12, max(0.04, abs(signal_score) * max(confidence, 0.4)))
    if signal_score < -0.30:
        return "underweight", min(0.12, max(0.04, abs(signal_score) * max(confidence, 0.4)))
    if signal_score < -0.05:
        return "sell", min(0.12, max(0.04, abs(signal_score) * max(confidence, 0.4)))
    return "hold", min(0.12, max(0.0, abs(signal_score) * max(confidence, 0.4)))
