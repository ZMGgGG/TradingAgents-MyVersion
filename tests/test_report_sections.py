from pathlib import Path

import pytest

from cli.main import save_report_to_disk


@pytest.mark.unit
def test_save_report_to_disk_includes_evidence_ledgers(tmp_path: Path):
    final_state = {
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "judge_decision": "",
        },
        "trader_investment_plan": "",
        "risk_debate_state": {
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "judge_decision": "",
        },
        "alpha_mining_result": {},
        "alpha_experience_summary": {
            "registry_entry_count": 2,
            "history_episode_count": 4,
            "used_registry_experience": True,
        },
        "factor_score": {},
        "position_sizing": {},
        "risk_gate_result": {},
        "execution_plan": {},
        "market_evidence_ledger": {"ticker": "300308.SZ"},
        "sentiment_evidence_ledger": {"source_coverage": 0.33},
        "news_evidence_ledger": {"source_diversity": 2},
        "fundamentals_evidence_ledger": {"sources": ["get_fundamentals"]},
    }

    report_file = save_report_to_disk(final_state, "300308.SZ", tmp_path)
    text = report_file.read_text(encoding="utf-8")
    assert "## III-C. Alpha Experience Summary" in text
    assert "## III-D. Evidence Ledgers" in text
    assert "Market Evidence Ledger" in text
    assert "News Evidence Ledger" in text
