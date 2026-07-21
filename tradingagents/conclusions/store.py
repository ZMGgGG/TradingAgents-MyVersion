from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from .models import ConclusionBook, ConclusionEvent, ConclusionTrack, utc_now


class ConclusionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def load(self) -> ConclusionBook:
        if not self.path.exists():
            return ConclusionBook()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return ConclusionBook()
        if isinstance(data, list):
            data = {"tracks": data}
        if not isinstance(data, dict):
            return ConclusionBook()
        tracks = []
        for item in data.get("tracks", []):
            if not isinstance(item, dict):
                continue
            try:
                tracks.append(ConclusionTrack.model_validate(item))
            except Exception:
                continue
        return ConclusionBook(tracks=tracks, updated_at=str(data.get("updated_at") or utc_now()))

    def save(self, book: ConclusionBook) -> Path:
        with self._lock:
            book.updated_at = utc_now()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.path.with_name(f"{self.path.name}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
            tmp_file.write_text(book.model_dump_json(indent=2), encoding="utf-8")
            tmp_file.replace(self.path)
        return self.path

    def list_tracks(self) -> list[dict[str, Any]]:
        return [track.public_payload() for track in self.load().tracks]

    def add_track(self, payload: dict[str, Any]) -> ConclusionTrack:
        track = _track_from_payload(payload)
        with self._lock:
            book = self.load()
            book.tracks.insert(0, track)
            self.save(book)
        return track

    def update_track(
        self,
        conclusion_id: str,
        updates: dict[str, Any],
        event_type: str = "updated",
        note: str = "",
    ) -> ConclusionTrack:
        with self._lock:
            book = self.load()
            for index, track in enumerate(book.tracks):
                if track.conclusion_id != conclusion_id:
                    continue
                data = track.model_dump()
                for key, value in updates.items():
                    if key in data:
                        data[key] = value
                data["updated_at"] = utc_now()
                events = list(track.events)
                events.append(
                    ConclusionEvent(
                        event_type=event_type,
                        note=note,
                        payload={key: updates[key] for key in sorted(updates.keys())},
                    )
                )
                data["events"] = events
                updated = ConclusionTrack.model_validate(data)
                book.tracks[index] = updated
                self.save(book)
                return updated
        raise KeyError(conclusion_id)

    def delete_track(self, conclusion_id: str) -> ConclusionTrack:
        with self._lock:
            book = self.load()
            for index, track in enumerate(book.tracks):
                if track.conclusion_id != conclusion_id:
                    continue
                deleted = book.tracks.pop(index)
                self.save(book)
                return deleted
        raise KeyError(conclusion_id)


def _track_from_payload(payload: dict[str, Any]) -> ConclusionTrack:
    data = dict(payload or {})
    data.setdefault("conclusion_id", uuid.uuid4().hex[:12])
    data.setdefault("status", "tracking")
    data.setdefault("opened_at", utc_now())
    data.setdefault("created_at", utc_now())
    data.setdefault("updated_at", utc_now())
    data.setdefault("events", [])
    if not data["events"]:
        data["events"] = [ConclusionEvent(event_type="created", note="Conclusion entered tracking book.")]
    data["ticker"] = str(data.get("ticker") or "").strip().upper()
    if not data["ticker"]:
        raise ValueError("ticker is required")
    data["asset_type"] = str(data.get("asset_type") or "stock").strip().lower() or "stock"
    data["action"] = str(data.get("action") or "hold").strip().lower() or "hold"
    data["horizon_days"] = max(1, int(float(data.get("horizon_days") or 20)))
    data["target_position_size"] = float(data.get("target_position_size") or 0.0)
    return ConclusionTrack.model_validate(data)
