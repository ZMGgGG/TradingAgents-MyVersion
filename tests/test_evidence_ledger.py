import pytest

from tradingagents.agents.analysts.fundamentals_analyst import _build_fundamentals_evidence_ledger
from tradingagents.agents.analysts.news_analyst import _build_news_evidence_ledger
from tradingagents.agents.analysts.sentiment_analyst import _build_sentiment_evidence_ledger
from tradingagents.graph.propagation import Propagator


@pytest.mark.unit
def test_propagator_initializes_evidence_ledgers():
    state = Propagator().create_initial_state("600519.SS", "2025-02-18")
    assert state["market_evidence_ledger"] == {}
    assert state["sentiment_evidence_ledger"] == {}
    assert state["news_evidence_ledger"] == {}
    assert state["fundamentals_evidence_ledger"] == {}


@pytest.mark.unit
def test_build_sentiment_evidence_ledger_records_quality_metadata():
    ledger = _build_sentiment_evidence_ledger(
        ticker="000002.SS",
        start_date="2025-02-11",
        end_date="2025-02-18",
        source_status={"news": "ok", "stocktwits": "empty", "reddit": "empty"},
        source_coverage=0.33,
        quality_flags=["social_unavailable", "forum_unavailable"],
        quality_weight=0.8,
    )
    assert ledger["ticker"] == "000002.SS"
    assert ledger["source_status"]["news"] == "ok"
    assert ledger["source_coverage"] == 0.33
    assert ledger["quality_flags"] == ["social_unavailable", "forum_unavailable"]
    assert ledger["quality_weight"] == 0.8


@pytest.mark.unit
def test_build_news_evidence_ledger_records_discovery_metadata():
    class _Discovery:
        ticker = "300308.SZ"
        start_date = "2026-06-01"
        end_date = "2026-06-30"
        expanded_queries = ["300308.SZ", "300308 公告"]
        source_count = 3
        source_diversity = 2
        company_blocks = ["primary"]
        related_blocks = ["related"]
        macro_block = "macro"
        summary = "Expanded summary"

    ledger = _build_news_evidence_ledger(_Discovery())
    assert ledger["ticker"] == "300308.SZ"
    assert ledger["source_count"] == 3
    assert ledger["source_diversity"] == 2
    assert ledger["has_primary_content"] is True


@pytest.mark.unit
def test_build_fundamentals_evidence_ledger_records_sources():
    ledger = _build_fundamentals_evidence_ledger(
        ticker="600519.SS",
        as_of_date="2026-06-29",
        lookback_days=30,
    )
    assert ledger["ticker"] == "600519.SS"
    assert ledger["lookback_days"] == 30
    assert "get_balance_sheet" in ledger["sources"]
