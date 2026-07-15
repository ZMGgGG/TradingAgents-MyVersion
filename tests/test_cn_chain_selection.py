import copy
from unittest.mock import patch

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows.interface import _resolve_vendor_config, route_to_vendor
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
def test_cn_vendor_value_error_falls_back_for_non_cn_ticker(monkeypatch):
    with patch.dict(
        "tradingagents.dataflows.interface.VENDOR_METHODS",
        {
            "get_fundamentals": {
                "akshare_cn": lambda ticker, curr_date=None: (_ for _ in ()).throw(
                    ValueError(f"AKShare CN fundamentals vendor only supports .SS/.SZ tickers, got {ticker}")
                ),
                "yfinance": lambda ticker, curr_date=None: f"fallback fundamentals for {ticker}",
            }
        },
        clear=False,
    ):
        monkeypatch.setattr(
            "tradingagents.dataflows.interface.get_vendor",
            lambda category, method=None: "akshare_cn,yfinance",
        )
        result = route_to_vendor("get_fundamentals", "AAPL", "2026-05-29")
        assert "fallback fundamentals for AAPL" == result


@pytest.mark.unit
def test_cn_benchmark_map_present():
    cfg = copy.deepcopy(default_config.DEFAULT_CONFIG)
    assert cfg["benchmark_map"][".SS"] == "000300.SS"
    assert cfg["benchmark_map"][".SZ"] == "399001.SZ"
