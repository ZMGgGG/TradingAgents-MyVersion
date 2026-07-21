from datetime import datetime, timedelta, timezone

import pytest

from frontend import server
from tradingagents.conclusions import ConclusionStore, summarize_conclusions


@pytest.mark.unit
def test_conclusion_store_adds_and_reviews_track(tmp_path):
    store = ConclusionStore(tmp_path / "conclusion_tracks.json")

    track = store.add_track(
        {
            "ticker": "nvda",
            "asset_type": "stock",
            "thesis": "Demand remains resilient.",
            "action": "buy",
            "target_position_size": "0.10",
            "horizon_days": "30",
            "entry_price": 100.0,
            "current_price": 110.0,
        }
    )

    assert track.ticker == "NVDA"
    assert track.current_return() == pytest.approx(0.10)

    reviewed = store.update_track(
        track.conclusion_id,
        {"status": "validated", "review_notes": "Thesis played out."},
        event_type="review",
        note="Thesis played out.",
    )

    assert reviewed.status == "validated"
    assert reviewed.review_notes == "Thesis played out."
    assert reviewed.events[-1].event_type == "review"


@pytest.mark.unit
def test_conclusion_lifecycle_marks_due_review(tmp_path):
    store = ConclusionStore(tmp_path / "conclusion_tracks.json")
    opened_at = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    track = store.add_track(
        {
            "ticker": "BTC-USD",
            "asset_type": "crypto",
            "thesis": "ETF flows remain supportive.",
            "opened_at": opened_at,
            "horizon_days": 30,
        }
    )

    assert track.with_lifecycle_status().status == "due_review"


@pytest.mark.unit
def test_conclusion_summary_counts_statuses(tmp_path):
    store = ConclusionStore(tmp_path / "conclusion_tracks.json")
    store.add_track({"ticker": "AAPL", "current_price": 110.0, "entry_price": 100.0})
    second = store.add_track({"ticker": "MSFT", "current_price": 90.0, "entry_price": 100.0})
    store.update_track(second.conclusion_id, {"status": "invalidated"}, event_type="review")

    summary = summarize_conclusions(store.load().tracks)

    assert summary["track_total"] == 2
    assert summary["status_counts"]["tracking"] == 1
    assert summary["status_counts"]["invalidated"] == 1
    assert summary["positive_return_rate"] == pytest.approx(0.5)


@pytest.mark.unit
def test_conclusion_store_deletes_track(tmp_path):
    store = ConclusionStore(tmp_path / "conclusion_tracks.json")
    first = store.add_track({"ticker": "AAPL"})
    second = store.add_track({"ticker": "MSFT"})

    deleted = store.delete_track(first.conclusion_id)

    assert deleted.conclusion_id == first.conclusion_id
    assert [track.conclusion_id for track in store.load().tracks] == [second.conclusion_id]
    with pytest.raises(KeyError):
        store.delete_track(first.conclusion_id)


@pytest.mark.unit
def test_server_builds_conclusion_payload_from_run_snapshot():
    payload = server._conclusion_track_from_run_snapshot(
        {
            "run_id": "run-1",
            "payload": {
                "ticker": "NVDA",
                "asset_type": "stock",
                "analysis_date": "2026-07-01",
            },
            "result": {
                "rating": "Buy",
                "summary": "AI demand remains resilient.",
                "decision_details": {"time_horizon": "30 days"},
            },
            "attachments": {
                "execution_plan": {
                    "action": "buy",
                    "target_position_size": 0.12,
                },
                "factor_runtime_detail": {"composite_score": 0.31},
            },
        }
    )

    assert payload["source_run_id"] == "run-1"
    assert payload["ticker"] == "NVDA"
    assert payload["action"] == "buy"
    assert payload["target_position_size"] == pytest.approx(0.12)
    assert payload["horizon_days"] == 30
    assert payload["factor_score"]["composite_score"] == 0.31
