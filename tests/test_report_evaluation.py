import pytest

from tradingagents.evaluation import render_report_evaluation
from tradingagents.evaluation.report_evaluator import parse_report_evaluation


@pytest.mark.unit
def test_parse_report_evaluation_summary_block():
    text = """
EVALUATION_SUMMARY
FACTUAL_COVERAGE: 8
EVIDENCE_SUPPORT: 7.5
REASONING_CONSISTENCY: 7
RISK_AWARENESS: 6.5
ACTIONABILITY: 8.5
WRITING_QUALITY: 9
TOTAL_SCORE: 77.5
VERDICT: Strong report with a few missing risk caveats.
MISSING_POINTS: It missed margin pressure and benchmark comparison.
UNSUPPORTED_CLAIMS: The demand recovery claim was not supported by the reference.
CORRECTION_PLAN: Add margin analysis and remove unsupported demand language.
PROMPT_TUNING_NOTES: Ask analysts to cite reference-backed facts before conclusions.
END_EVALUATION_SUMMARY
"""
    result = parse_report_evaluation(text)
    assert result.factual_coverage == 8
    assert result.evidence_support == 7.5
    assert result.total_score == 77.5
    assert "margin pressure" in result.missing_points
    assert "unsupported demand" in result.correction_plan


@pytest.mark.unit
def test_render_report_evaluation_contains_scorecard_and_corrections():
    result = parse_report_evaluation(
        """
FACTUAL_COVERAGE: 5
EVIDENCE_SUPPORT: 5
REASONING_CONSISTENCY: 5
RISK_AWARENESS: 5
ACTIONABILITY: 5
WRITING_QUALITY: 5
VERDICT: Needs work.
MISSING_POINTS: Missing reference facts.
UNSUPPORTED_CLAIMS: Unsupported valuation call.
CORRECTION_PLAN: Add citations.
PROMPT_TUNING_NOTES: Tighten evidence instructions.
"""
    )
    markdown = render_report_evaluation(result)
    assert "# Research Report Evaluation" in markdown
    assert "- Total Score: 50.0/100" in markdown
    assert "Unsupported valuation call" in markdown
