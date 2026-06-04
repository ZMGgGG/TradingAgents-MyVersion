import copy

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows.interface import _resolve_vendor_config
from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
def test_cn_symbol_prefers_akshare_for_news_and_fundamentals():
    assert _resolve_vendor_config("news_data", "get_news", "600519.SS", "2026-05-01", "2026-05-29") == "akshare_cn,yfinance"
    assert _resolve_vendor_config("fundamental_data", "get_fundamentals", "600519.SS", "2026-05-29") == "akshare_cn,yfinance"
    assert _resolve_vendor_config("news_data", "get_insider_transactions", "600519.SS") == "akshare_cn,yfinance"


@pytest.mark.unit
def test_us_symbol_keeps_default_vendor_chain():
    assert _resolve_vendor_config("news_data", "get_news", "AAPL", "2026-05-01", "2026-05-29") == "yfinance"


@pytest.mark.unit
def test_cn_benchmark_map_present():
    cfg = copy.deepcopy(default_config.DEFAULT_CONFIG)
    assert cfg["benchmark_map"][".SS"] == "000300.SS"
    assert cfg["benchmark_map"][".SZ"] == "399001.SZ"
