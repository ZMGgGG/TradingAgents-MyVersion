import pytest

from tradingagents.core.data_snapshot import DataSnapshot
from tradingagents.core.time_context import TimeContext, coerce_time_context
from tradingagents.graph.propagation import Propagator


@pytest.mark.unit
def test_time_context_from_trade_date():
    ctx = TimeContext.from_trade_date("2026-05-01")
    assert ctx.trade_date == "2026-05-01"
    assert ctx.as_of_date == "2026-05-01"
    assert "Use only information" in ctx.to_prompt_string()


@pytest.mark.unit
def test_coerce_time_context_from_mapping():
    ctx = coerce_time_context({"trade_date": "2026-05-01", "as_of_date": "2026-05-01"}, "2026-05-01")
    assert ctx.as_of_date == "2026-05-01"


@pytest.mark.unit
def test_propagator_initial_state_includes_time_context():
    state = Propagator().create_initial_state("NVDA", "2026-05-01")
    assert state["time_context"]["as_of_date"] == "2026-05-01"
    assert state["investment_debate_state"]["signal_score"] == 0.0


@pytest.mark.unit
def test_data_snapshot_from_state():
    state = Propagator().create_initial_state("NVDA", "2026-05-01")
    state.update(
        {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "plan",
            "trader_investment_plan": "trader",
            "final_trade_decision": "Rating: Buy",
        }
    )
    snapshot = DataSnapshot.from_state(state)
    assert snapshot.snapshot_id == "NVDA:2026-05-01"
    assert snapshot.reports["market_report"] == "market"
