from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class AlphaCandidate(BaseModel):
    """A mined alpha idea with a human hypothesis and executable-style expression."""

    name: str
    hypothesis: str
    expression: str
    signal_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    complexity: int = Field(ge=1)
    validation_status: str
    evidence: List[str] = Field(default_factory=list)


class AlphaMiningResult(BaseModel):
    """Compact QuantaAlpha-style result consumed by the deterministic factor layer."""

    enabled: bool = True
    selected_alpha: AlphaCandidate | None = None
    signal_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    stability: float = Field(default=0.0, ge=0.0, le=1.0)
    redundancy_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    candidates: List[AlphaCandidate] = Field(default_factory=list)
    summary: str = ""
