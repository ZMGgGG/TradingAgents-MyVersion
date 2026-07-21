import pytest

from tradingagents.papertrading.analytics import list_paper_analytics_skills, run_paper_analytics


@pytest.mark.unit
def test_paper_analytics_payload_computes_core_metrics():
    payload = run_paper_analytics(
        {
            "initial_cash": 100000.0,
            "snapshots": [
                {
                    "trade_date": "2026-05-01T00:00:00",
                    "cash": 90000.0,
                    "positions_value": 10000.0,
                    "equity": 100000.0,
                    "total_return": 0.0,
                },
                {
                    "trade_date": "2026-05-02T00:00:00",
                    "cash": 90000.0,
                    "positions_value": 12000.0,
                    "equity": 102000.0,
                    "total_return": 0.02,
                },
                {
                    "trade_date": "2026-05-03T00:00:00",
                    "cash": 90000.0,
                    "positions_value": 11000.0,
                    "equity": 101000.0,
                    "total_return": 0.01,
                },
            ],
        }
    )

    assert "builtin_performance" in payload["skills"]
    assert payload["summary"]["observations"] == 3
    assert payload["summary"]["total_return"] == pytest.approx(0.01)
    assert payload["summary"]["max_drawdown"] < 0
    assert payload["summary"]["win_rate"] == pytest.approx(0.5)


@pytest.mark.unit
def test_paper_analytics_skills_are_discoverable():
    skills = list_paper_analytics_skills()
    names = {item["name"] for item in skills}

    assert "builtin_performance" in names
    assert "conclusion_lifecycle" in names
    assert any(item["default_enabled"] for item in skills if item["name"] == "builtin_performance")


@pytest.mark.unit
def test_paper_analytics_can_run_requested_lifecycle_skill_only():
    payload = run_paper_analytics(
        {
            "initial_cash": 100000.0,
            "positions": {"NVDA": {"ticker": "NVDA", "quantity": 1.0, "last_price": 110.0}},
            "fills": [
                {
                    "ticker": "NVDA",
                    "trade_date": "2026-05-01T00:00:00",
                    "side": "buy",
                    "price": 100.0,
                    "horizon_days": 30,
                    "target_position_size": 0.1,
                    "thesis": "Demand remains resilient.",
                }
            ],
        },
        requested=["conclusion_lifecycle"],
    )

    assert payload["skills"] == ["conclusion_lifecycle"]
    assert payload["returns"] == []
    assert payload["summary"]["track_total"] == 1
    assert payload["tracks"][0]["current_return"] == pytest.approx(0.1)
