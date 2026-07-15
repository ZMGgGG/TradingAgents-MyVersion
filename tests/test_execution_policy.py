import pytest

from tradingagents.decisioning.execution_policy import (
    candidate_signal_to_execution,
    normalize_target_position_size,
)


@pytest.mark.unit
def test_candidate_signal_to_execution_maps_strong_positive_to_overweight():
    action, size = candidate_signal_to_execution(0.45, 0.8)
    assert action == "overweight"
    assert size > 0


@pytest.mark.unit
def test_candidate_signal_to_execution_maps_mild_negative_to_sell():
    action, size = candidate_signal_to_execution(-0.10, 0.7)
    assert action == "sell"
    assert size > 0


@pytest.mark.unit
def test_candidate_signal_to_execution_maps_strong_negative_to_underweight():
    action, size = candidate_signal_to_execution(-0.45, 0.8)
    assert action == "underweight"
    assert size > 0


@pytest.mark.unit
def test_candidate_signal_to_execution_maps_neutral_to_hold():
    action, size = candidate_signal_to_execution(0.01, 0.7)
    assert action == "hold"
    assert size >= 0


@pytest.mark.unit
def test_hold_execution_normalizes_target_position_to_zero():
    assert normalize_target_position_size("hold", 0.05) == 0.0
