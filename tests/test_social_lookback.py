import json
from datetime import datetime, timedelta, timezone

import pytest

from tradingagents.dataflows.reddit import fetch_reddit_posts
from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages


@pytest.mark.unit
def test_stocktwits_respects_lookback_window(monkeypatch):
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat().replace("+00:00", "Z")
    payload = {
        "messages": [
            {"created_at": recent, "user": {"username": "u1"}, "entities": {"sentiment": {"basic": "Bullish"}}, "body": "recent"},
            {"created_at": old, "user": {"username": "u2"}, "entities": {"sentiment": {"basic": "Bearish"}}, "body": "old"},
        ]
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("tradingagents.dataflows.stocktwits.urlopen", lambda *args, **kwargs: _Resp())
    text = fetch_stocktwits_messages("AAPL", lookback_days=7)
    assert "recent" in text
    assert "old" not in text


@pytest.mark.unit
def test_reddit_uses_broader_time_filter_for_longer_lookback(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            payload = {"data": {"children": []}}
            return json.dumps(payload).encode("utf-8")

    def _urlopen(req, timeout=10.0):
        captured["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr("tradingagents.dataflows.reddit.urlopen", _urlopen)
    fetch_reddit_posts("AAPL", lookback_days=30)
    assert "t=month" in captured["url"]
