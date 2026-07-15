from types import SimpleNamespace

from tradingagents.agents.analysts.market_analyst import _should_enable_market_tools
from tradingagents.agents.analysts.news_analyst import _should_enable_news_tools
from tradingagents.agents.analysts.sentiment_analyst import _should_enable_sentiment_tools


def test_market_tools_stay_disabled_when_prefetch_is_complete():
    assert not _should_enable_market_tools(
        {
            "asset_type": "stock",
            "price_block": "# Stock data\nDate,Close\n2026-01-01,100",
            "indicator_block": "## rsi values\nDate,rsi\n2026-01-01,55",
        }
    )


def test_market_tools_enable_when_prefetch_degrades():
    assert _should_enable_market_tools(
        {
            "asset_type": "stock",
            "price_block": "Price data unavailable: vendor timeout",
            "indicator_block": "## rsi values\nDate,rsi\n2026-01-01,55",
        }
    )


def test_sentiment_tools_enable_only_for_sparse_coverage():
    assert not _should_enable_sentiment_tools(
        {"news": "ok", "stocktwits": "ok", "reddit": "empty"},
        2 / 3,
    )
    assert _should_enable_sentiment_tools(
        {"news": "empty", "stocktwits": "empty", "reddit": "ok"},
        1 / 3,
    )


def test_news_tools_enable_when_discovery_has_no_sources():
    assert _should_enable_news_tools(
        SimpleNamespace(
            source_count=0,
            company_blocks=[],
            related_blocks=[],
            macro_block="",
        )
    )
    assert not _should_enable_news_tools(
        SimpleNamespace(
            source_count=3,
            company_blocks=["company news"],
            related_blocks=[],
            macro_block="",
        )
    )
