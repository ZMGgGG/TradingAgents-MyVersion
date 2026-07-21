import pandas as pd
import pytest

from tradingagents.papertrading import PaperBroker, PaperOrder, PaperTradingRunner, build_order_from_final_state


def _price_loader(_ticker, _start_date, _end_date):
    return pd.DataFrame(
        {"Close": [100.0, 105.0, 110.0]},
        index=pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-03"]),
    )


@pytest.mark.unit
def test_build_order_from_final_state_uses_execution_plan():
    order = build_order_from_final_state(
        "NVDA",
        "2026-05-01",
        {
            "final_trade_decision": "**Rating**: Buy",
            "execution_plan": {
                "action": "buy",
                "target_position_size": 0.10,
                "risk_gate_approved": True,
            },
        },
    )

    assert order.rating == "Buy"
    assert order.action == "buy"
    assert order.target_position_size == 0.10
    assert order.risk_gate_approved is True


@pytest.mark.unit
def test_paper_runner_buys_target_weight_and_marks_to_market():
    runner = PaperTradingRunner(_price_loader)
    result = runner.run_from_final_state(
        "NVDA",
        "2026-05-01",
        {
            "final_trade_decision": "**Rating**: Buy",
            "execution_plan": {
                "action": "buy",
                "target_position_size": 0.10,
                "risk_gate_approved": True,
            },
        },
        holding_days=2,
        initial_capital=100000.0,
    )

    assert result.resolved is True
    assert len(result.fills) == 1
    assert result.fills[0].side == "buy"
    assert result.fills[0].quantity == pytest.approx(100.0)
    assert result.snapshots[-1].equity == pytest.approx(101000.0)
    assert result.snapshots[-1].total_return == pytest.approx(0.01)


@pytest.mark.unit
def test_paper_runner_hold_zero_target_does_not_trade():
    runner = PaperTradingRunner(_price_loader)
    result = runner.run_from_final_state(
        "NVDA",
        "2026-05-01",
        {
            "final_trade_decision": "**Rating**: Hold",
            "execution_plan": {
                "action": "hold",
                "target_position_size": 0.0,
                "risk_gate_approved": True,
            },
        },
        holding_days=2,
        initial_capital=100000.0,
    )

    assert result.fills == []
    assert result.snapshots[-1].equity == pytest.approx(100000.0)
    assert result.snapshots[-1].positions == {}


@pytest.mark.unit
def test_paper_runner_blocked_by_risk_gate_does_not_trade():
    runner = PaperTradingRunner(_price_loader)
    result = runner.run_from_final_state(
        "NVDA",
        "2026-05-01",
        {
            "final_trade_decision": "**Rating**: Buy",
            "execution_plan": {
                "action": "buy",
                "target_position_size": 0.10,
                "risk_gate_approved": False,
            },
        },
        holding_days=2,
        initial_capital=100000.0,
    )

    assert result.fills == []
    assert result.snapshots[-1].equity == pytest.approx(100000.0)
    assert result.snapshots[-1].positions == {}


@pytest.mark.unit
def test_paper_runner_applies_commission_and_slippage():
    runner = PaperTradingRunner(_price_loader)
    result = runner.run_from_final_state(
        "NVDA",
        "2026-05-01",
        {
            "final_trade_decision": "**Rating**: Buy",
            "execution_plan": {
                "action": "buy",
                "target_position_size": 0.10,
                "risk_gate_approved": True,
            },
        },
        holding_days=2,
        initial_capital=100000.0,
        commission_rate=0.001,
        slippage_rate=0.01,
    )

    assert result.fills[0].price == pytest.approx(101.0)
    assert result.fills[0].commission == pytest.approx(10.0)
    assert result.snapshots[-1].equity < 101000.0


@pytest.mark.unit
def test_paper_fill_keeps_research_tracking_metadata():
    broker = PaperBroker(initial_cash=100000.0)
    fill = broker.submit_order(
        PaperOrder(
            ticker="NVDA",
            trade_date="2026-05-01",
            rating="Buy",
            action="buy",
            target_position_size=0.10,
            risk_gate_approved=True,
            source_run_id="run-123",
            thesis="AI demand remains resilient.",
            horizon_days=30,
        ),
        price=100.0,
    )

    assert fill is not None
    assert fill.source_run_id == "run-123"
    assert fill.thesis == "AI demand remains resilient."
    assert fill.horizon_days == 30
    assert fill.target_position_size == pytest.approx(0.10)
