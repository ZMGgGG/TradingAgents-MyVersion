import pytest

from tradingagents.agents.schemas import parse_analyst_feature_summary


@pytest.mark.unit
def test_parse_analyst_feature_summary_reads_quality_fields():
    text = """
FEATURE_SUMMARY
SCORE: 0.25
CONFIDENCE: 0.60
KEY_SIGNAL: News-led constructive tone
RISK_FLAG: Social coverage is sparse
SOURCE_COVERAGE: 0.33
QUALITY_FLAGS: social_unavailable | future_dated_news
QUALITY_WEIGHT: 0.65
END_FEATURE_SUMMARY
"""
    result = parse_analyst_feature_summary(text)
    assert result.score == 0.25
    assert result.source_coverage == 0.33
    assert result.quality_flags == ["social_unavailable", "future_dated_news"]
    assert result.quality_weight == 0.65
