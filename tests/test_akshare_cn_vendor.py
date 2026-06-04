import copy

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows.config import get_config, set_config
from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
def test_cn_ticker_prefers_akshare_for_market_tools(mock_llm_client):
    set_config(copy.deepcopy(default_config.DEFAULT_CONFIG))
    graph = TradingAgentsGraph(debug=False)
    graph.ticker = "600519.SS"
    set_config({"_current_ticker": "600519.SS"})
    cfg = get_config()
    assert cfg["tool_vendors"]["get_stock_data"] == "akshare_cn,yfinance"
    assert cfg["tool_vendors"]["get_indicators"] == "akshare_cn,yfinance"


@pytest.mark.unit
def test_us_ticker_keeps_default_market_tools(mock_llm_client):
    set_config(copy.deepcopy(default_config.DEFAULT_CONFIG))
    set_config({"_current_ticker": "AAPL"})
    cfg = get_config()
    assert "get_stock_data" not in cfg["tool_vendors"]
    assert "get_indicators" not in cfg["tool_vendors"]
