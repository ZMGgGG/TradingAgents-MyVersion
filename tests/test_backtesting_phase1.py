from unittest.mock import MagicMock

import pytest

from tradingagents.backtesting.engine import BacktestScenario, BatchBacktester
from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
def test_batch_backtester_runs_from_final_states_without_propagate():
    graph = MagicMock()
    graph._resolve_benchmark.return_value = "SPY"
    graph._fetch_returns.return_value = (0.05, 0.02, 5)

    backtester = BatchBacktester(graph)
    result = backtester.run_from_final_states(
        [
            BacktestScenario(ticker="NVDA", trade_date="2026-05-01"),
        ],
        [
            {
                "final_trade_decision": "**Rating**: Buy",
                "investment_debate_state": {"signal_confidence": 0.8},
            }
        ],
        holding_days=5,
    )

    graph.propagate.assert_not_called()
    assert len(result.trades) == 1
    assert result.trades[0].rating == "Buy"
    assert result.metrics.trade_count == 1


@pytest.mark.unit
def test_fetch_returns_falls_back_when_benchmark_missing(monkeypatch):
    class _Series:
        def __init__(self, values):
            self._values = values

        @property
        def iloc(self):
            return self

        def __getitem__(self, idx):
            return self._values[idx]

    class _History:
        def __init__(self, closes):
            self._close = _Series(closes)

        def __len__(self):
            return len(self._close._values)

        def __getitem__(self, key):
            if key == "Close":
                return self._close
            raise KeyError(key)

    class _Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, start=None, end=None):
            if self.symbol == "MISSING_BENCH":
                return _History([100.0])
            return _History([100.0, 105.0, 106.0])

    monkeypatch.setattr("tradingagents.graph.trading_graph.yf.Ticker", _Ticker)

    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    raw, alpha, days = TradingAgentsGraph._fetch_returns(
        graph,
        "NVDA",
        "2026-05-01",
        holding_days=2,
        benchmark="MISSING_BENCH",
    )

    assert raw is not None
    assert alpha == 0.0
    assert days == 2


@pytest.mark.unit
def test_fetch_returns_uses_vendor_price_payload(monkeypatch):
    payload = (
        "# Stock data for NVDA from 2026-05-01 to 2026-05-10\n"
        "# Total records: 3\n\n"
        "Date,Open,High,Low,Close,Volume\n"
        "2026-05-01,100,101,99,100,1000\n"
        "2026-05-02,104,105,103,105,1200\n"
        "2026-05-03,106,107,105,106,900\n"
    )

    def _route(method, symbol, start, end):
        return payload

    monkeypatch.setattr("tradingagents.graph.trading_graph.route_to_vendor", _route)

    class _Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, start=None, end=None):
            raise AssertionError("yfinance fallback should not be used when vendor payload parses")

    monkeypatch.setattr("tradingagents.graph.trading_graph.yf.Ticker", _Ticker)

    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    raw, alpha, days = TradingAgentsGraph._fetch_returns(
        graph,
        "NVDA",
        "2026-05-01",
        holding_days=2,
        benchmark="SPY",
    )

    assert raw is not None
    assert alpha is not None
    assert days == 2
