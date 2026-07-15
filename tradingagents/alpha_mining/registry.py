from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json


@dataclass
class AlphaRegistryEntry:
    name: str
    hypothesis: str
    expression: str
    signal_score: float
    confidence: float
    stability: float
    redundancy_penalty: float
    asset_type: str = "stock"
    evidence: list[str] = field(default_factory=list)
    source: str = ""
    trade_date: str = ""
    realized_return: float = 0.0
    realized_alpha: float = 0.0
    evaluation_score: float = 0.0
    sample_count: int = 1
    recent_realized_alpha: float = 0.0


class AlphaRegistry:
    """Persistent registry for validated alpha candidates."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def upsert(self, entry: AlphaRegistryEntry) -> Path:
        entries = self.load()
        key = entry.expression
        existing = next((row for row in entries if row.get("expression") == key), None)
        filtered = [row for row in entries if row.get("expression") != key]

        merged_sample_count = entry.sample_count
        merged_realized_return = entry.realized_return
        merged_realized_alpha = entry.realized_alpha
        merged_evaluation_score = entry.evaluation_score
        if existing is not None:
            existing_count = int(existing.get("sample_count", 1))
            merged_sample_count = existing_count + 1
            merged_realized_return = (
                float(existing.get("realized_return", 0.0)) * existing_count + entry.realized_return
            ) / merged_sample_count
            merged_realized_alpha = (
                float(existing.get("realized_alpha", 0.0)) * existing_count + entry.realized_alpha
            ) / merged_sample_count
            merged_evaluation_score = (
                float(existing.get("evaluation_score", 0.0)) * existing_count + entry.evaluation_score
            ) / merged_sample_count

        filtered.append(
            {
                "name": entry.name,
                "hypothesis": entry.hypothesis,
                "expression": entry.expression,
                "signal_score": entry.signal_score,
                "confidence": entry.confidence,
                "stability": entry.stability,
                "redundancy_penalty": entry.redundancy_penalty,
                "asset_type": getattr(entry, "asset_type", "stock") or "stock",
                "evidence": entry.evidence,
                "source": entry.source,
                "trade_date": entry.trade_date,
                "realized_return": merged_realized_return,
                "realized_alpha": merged_realized_alpha,
                "evaluation_score": merged_evaluation_score,
                "sample_count": merged_sample_count,
                "recent_realized_alpha": entry.realized_alpha,
            }
        )
        filtered = self._prune_entries(filtered)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path

    def write_entries(self, entries: list[dict[str, Any]]) -> Path:
        entries = self._prune_entries(entries)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path

    def _prune_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = sorted(
            entries,
            key=lambda row: (
                float(row.get("evaluation_score", 0.0)),
                float(row.get("realized_alpha", 0.0)),
                row.get("trade_date", ""),
            ),
            reverse=True,
        )
        deduped: dict[str, dict[str, Any]] = {}
        for row in ranked:
            expression = str(row.get("expression", ""))
            if not expression:
                continue
            if expression not in deduped:
                deduped[expression] = row
        return list(deduped.values())[-50:]
