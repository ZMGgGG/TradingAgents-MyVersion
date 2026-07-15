import pytest
import pandas as pd

from tradingagents.content_discovery.planner import (
    _fetch_cn_related_block,
    build_expanded_queries,
    discover_related_content,
    render_discovery_context,
)


@pytest.mark.unit
def test_build_expanded_queries_for_cn_equity():
    queries = build_expanded_queries("300308.SZ")
    assert "300308.SZ" in queries
    assert "300308 公告" in queries
    assert "300308 业绩" in queries
    assert "300308 龙虎榜" in queries
    assert "300308 概念" in queries


@pytest.mark.unit
def test_build_expanded_queries_for_crypto():
    queries = build_expanded_queries("ETH-USD", asset_type="crypto")
    assert "ETH-USD" in queries
    assert "ETH crypto" in queries


@pytest.mark.unit
def test_discover_related_content_aggregates_primary_related_and_macro(monkeypatch):
    def _route(method, *args):
        if method == "get_global_news":
            return "## Global Market News\n\n### macro\nsummary"
        query = args[0]
        return f"## {query} News\n\n### headline\nsummary"

    monkeypatch.setattr("tradingagents.content_discovery.planner.route_to_vendor", _route)

    result = discover_related_content(
        ticker="300308.SZ",
        start_date="2026-06-01",
        end_date="2026-06-30",
        lookback_days=30,
    )

    assert result.company_blocks
    assert result.related_blocks
    assert result.macro_block
    assert result.source_count >= 2
    rendered = render_discovery_context(result)
    assert "Expanded queries" in rendered
    assert "Primary ticker/company content" in rendered


@pytest.mark.unit
def test_cn_related_queries_use_cn_specific_proxy(monkeypatch):
    class _AK:
        pass

    def _fetcher(symbol=None):
        return pd.DataFrame({"代码": ["300308"], "热度": [1]})

    _fetcher.__name__ = "stock_hot_rank_detail_em"
    _AK.stock_hot_rank_detail_em = _fetcher
    _AK.stock_comment_em = None
    _AK.stock_hot_rank_em = None
    _AK.stock_individual_notice_report = None
    _AK.stock_notice_report = None

    monkeypatch.setattr("tradingagents.content_discovery.planner.route_to_vendor", lambda *args, **kwargs: "## fallback")
    import sys
    monkeypatch.setitem(sys.modules, "akshare", _AK)
    block = _fetch_cn_related_block("300308 龙虎榜", "300308.SZ", "2026-06-01", "2026-06-30")
    assert "retail proxy block" in block


@pytest.mark.unit
def test_cn_alias_cache_persists_aliases(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tradingagents.content_discovery.planner.route_to_vendor",
        lambda *args, **kwargs: "# CN Company Fundamentals for 300308.SZ\n名称: 测试公司\n股票简称: 测试简称\n",
    )

    queries = build_expanded_queries("300308.SZ")
    assert "测试公司" in queries
    assert "测试简称" in queries


@pytest.mark.unit
def test_discovery_cache_reuses_saved_result(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    call_count = {"count": 0}

    def _route(method, *args):
        call_count["count"] += 1
        if method == "get_global_news":
            return "## Global Market News\n\n### macro\nsummary"
        query = args[0]
        return f"## {query} News\n\n### headline\nsummary"

    monkeypatch.setattr("tradingagents.content_discovery.planner.route_to_vendor", _route)

    discover_related_content(
        ticker="300308.SZ",
        start_date="2026-06-01",
        end_date="2026-06-30",
        lookback_days=30,
    )
    first_count = call_count["count"]
    discover_related_content(
        ticker="300308.SZ",
        start_date="2026-06-01",
        end_date="2026-06-30",
        lookback_days=30,
    )
    assert call_count["count"] == first_count
