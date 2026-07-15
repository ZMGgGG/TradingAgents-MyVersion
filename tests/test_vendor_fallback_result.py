import copy

import pytest

import tradingagents.default_config as default_config
import tradingagents.dataflows.interface as interface
from tradingagents.dataflows.config import set_config


@pytest.mark.unit
def test_route_to_vendor_falls_back_on_unavailable_string(monkeypatch):
    set_config(copy.deepcopy(default_config.DEFAULT_CONFIG))

    monkeypatch.setitem(
        interface.VENDOR_METHODS,
        "get_stock_data",
        {
            "akshare_cn": lambda *args, **kwargs: "No AKShare CN stock data found for symbol '600519.SS' between 2026-05-01 and 2026-05-31",
            "yfinance": lambda *args, **kwargs: "# Stock data for 600519.SS from 2026-05-01 to 2026-05-31\nDate,Close\n2026-05-01,100\n",
        },
    )

    result = interface.route_to_vendor(
        "get_stock_data",
        "600519.SS",
        "2026-05-01",
        "2026-05-31",
    )

    assert result.startswith("# Stock data for 600519.SS")
