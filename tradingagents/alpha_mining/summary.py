from __future__ import annotations

from datetime import datetime
from typing import Any

from .i18n import alpha_text


def build_alpha_experience_summary(
    registry_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    selected_alpha: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact summary of alpha experience reuse and recent performance."""
    selected_alpha = selected_alpha or {}
    selected_name = str(selected_alpha.get("name", ""))
    selected_status = str(selected_alpha.get("validation_status", ""))

    weighted_rows = [(row, _time_decay_weight(str(row.get("trade_date", "")))) for row in registry_rows]
    total_weight = sum(weight for _, weight in weighted_rows) or 1.0
    realized_returns = [float(row.get("realized_return", 0.0)) * weight for row, weight in weighted_rows]
    realized_alphas = [float(row.get("realized_alpha", 0.0)) * weight for row, weight in weighted_rows]
    evaluation_scores = [float(row.get("evaluation_score", 0.0)) * weight for row, weight in weighted_rows]
    sample_counts = [int(row.get("sample_count", 1)) for row in registry_rows]
    recent_realized_alphas = [float(row.get("recent_realized_alpha", row.get("realized_alpha", 0.0))) for row in registry_rows]
    positive_alpha_count = sum(1 for value in realized_alphas if value > 0)
    win_rate = (positive_alpha_count / len(weighted_rows)) if weighted_rows else 0.0

    recent_history = history_rows[-5:]
    recent_names = [
        str(item.get("payload", {}).get("alpha_result", {}).get("selected_alpha", {}).get("name", ""))
        for item in recent_history
    ]
    selected_registry_row = next(
        (row for row in registry_rows if selected_name and selected_name.replace("registry_", "", 1) in str(row.get("name", ""))),
        None,
    )
    selected_sample_count = int(selected_registry_row.get("sample_count", 0)) if selected_registry_row else 0
    registry_reuse_ready = selected_status == "registry_reuse" and selected_sample_count >= 2

    return {
        "registry_entry_count": len(registry_rows),
        "history_episode_count": len(history_rows),
        "selected_alpha_name": selected_name,
        "selected_alpha_status": selected_status,
        "used_registry_experience": registry_reuse_ready,
        "experience_summary": alpha_text(
            f"Selected={selected_name or 'none'}, status={selected_status or 'none'}, registry_entries={len(registry_rows)}, history_episodes={len(history_rows)}.",
            f"当前选中={selected_name or '无'}，状态={selected_status or '无'}，registry条目={len(registry_rows)}，history轨迹={len(history_rows)}。",
        ),
        "average_realized_return": (sum(realized_returns) / total_weight) if realized_returns else 0.0,
        "average_realized_alpha": (sum(realized_alphas) / total_weight) if realized_alphas else 0.0,
        "average_evaluation_score": (sum(evaluation_scores) / total_weight) if evaluation_scores else 0.0,
        "average_sample_count": (sum(sample_counts) / len(sample_counts)) if sample_counts else 0.0,
        "average_recent_realized_alpha": (sum(recent_realized_alphas) / len(recent_realized_alphas)) if recent_realized_alphas else 0.0,
        "selected_alpha_sample_count": selected_sample_count,
        "positive_alpha_win_rate": win_rate,
        "recent_alpha_names": [name for name in recent_names if name],
    }


def _time_decay_weight(trade_date: str) -> float:
    try:
        dt = datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        return 1.0
    age_days = max(0, (datetime.now() - dt).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.8
    if age_days <= 180:
        return 0.6
    return 0.4
