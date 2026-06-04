import pytest

from tradingagents.decisioning.factor_engine import FactorEngine
from tradingagents.decisioning.position_sizing import PositionSizer
from tradingagents.decisioning.risk_gate import RiskGate


@pytest.mark.unit
def test_factor_engine_scores_reports_and_debate():
    engine = FactorEngine()
    state = {
        "market_report": "strong bullish momentum and positive upside",
        "fundamentals_report": "strong growth and positive fundamentals",
        "sentiment_report": "bullish retail sentiment remains constructive",
        "news_report": "positive macro and growth narrative",
        "investment_debate_state": {"signal_score": 0.4},
        "risk_debate_state": {"signal_score": -0.1},
    }
    score = engine.score(state)
    assert score.composite_score > 0
    assert "composite" in score.summary


@pytest.mark.unit
def test_factor_engine_prefers_structured_feature_scores():
    engine = FactorEngine()
    state = {
        "market_report": "negative words should not dominate",
        "fundamentals_report": "negative words should not dominate",
        "sentiment_report": "negative words should not dominate",
        "news_report": "negative words should not dominate",
        "market_features": {"score": 0.8},
        "fundamentals_features": {"score": 0.6},
        "sentiment_features": {"score": 0.4},
        "news_features": {"score": 0.2},
        "investment_debate_state": {"signal_score": 0.3},
        "risk_debate_state": {"signal_score": 0.0},
    }
    score = engine.score(state)
    assert score.technical == 0.8
    assert score.fundamentals == 0.6
    assert score.sentiment == 0.4
    assert score.news == 0.2


@pytest.mark.unit
def test_position_sizer_creates_target_position():
    sizer = PositionSizer()
    state = {
        "investment_debate_state": {"signal_confidence": 0.8},
        "factor_score": {"composite_score": 0.5},
        "risk_debate_state": {"signal_score": 0.1},
    }
    plan = sizer.size(state)
    assert plan.target_position_size > 0
    assert plan.target_position_size <= plan.max_position_size


@pytest.mark.unit
def test_risk_gate_blocks_low_confidence_trade():
    gate = RiskGate(min_confidence=0.6)
    state = {
        "investment_debate_state": {"signal_confidence": 0.4},
        "factor_score": {"composite_score": 0.3},
        "risk_debate_state": {"signal_score": 0.0},
        "position_sizing": {"target_position_size": 0.08},
    }
    result = gate.evaluate(state)
    assert result.approved is False
    assert result.forced_rating == "Hold"
