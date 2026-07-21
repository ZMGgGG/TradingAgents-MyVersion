from __future__ import annotations

from collections import Counter
from typing import Any

from .models import ConclusionTrack


def summarize_conclusions(tracks: list[ConclusionTrack]) -> dict[str, Any]:
    status_counts = Counter(track.with_lifecycle_status().status for track in tracks)
    returns = [
        value
        for value in (track.current_return() for track in tracks)
        if value is not None
    ]
    positive = len([value for value in returns if value > 0])
    alpha_values = [track.alpha_return for track in tracks if track.alpha_return is not None]
    return {
        "track_total": len(tracks),
        "status_counts": dict(status_counts),
        "tracked_return_count": len(returns),
        "positive_return_rate": positive / len(returns) if returns else 0.0,
        "average_return": sum(returns) / len(returns) if returns else 0.0,
        "average_alpha": sum(alpha_values) / len(alpha_values) if alpha_values else 0.0,
    }

