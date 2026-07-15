from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AlphaMiningEpisode:
    """One mined alpha attempt plus its downstream validation signals."""

    source: str
    ticker: str
    trade_date: str
    payload: dict[str, Any]
    asset_type: str = "stock"
    created_at_utc: str = field(default_factory=_utc_now)


class AlphaMiningHistory:
    """Read/write a lightweight local alpha-mining history file."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def append(self, episode: AlphaMiningEpisode) -> Path:
        entries = self.load()
        entries.append(
            {
                "source": episode.source,
                "ticker": episode.ticker,
                "trade_date": episode.trade_date,
                "asset_type": getattr(episode, "asset_type", "stock") or "stock",
                "payload": episode.payload,
                "created_at_utc": episode.created_at_utc,
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path
