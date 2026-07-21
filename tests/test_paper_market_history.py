import pytest

from frontend.server import (
    _live_market_quote,
    _mark_paper_account,
    _paper_account_file,
    _remember_paper_market_history,
    _save_paper_account,
)


def _quote(ticker):
    return {
        "market_ticker": ticker,
        "history": [
            {"date": "2026-07-14", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1},
            {"date": "2026-07-15", "open": 105.0, "high": 112.0, "low": 101.0, "close": 110.0, "volume": 2},
        ],
    }


@pytest.mark.unit
def test_paper_market_history_persists_btc_and_eth_only():
    account = {"market_history": {}}

    assert _remember_paper_market_history(account, _quote("BTC-USD")) is True
    assert _remember_paper_market_history(account, _quote("ETH-USD")) is True
    assert _remember_paper_market_history(account, _quote("AAPL")) is False

    assert "BTC-USD" in account["market_history"]
    assert "ETH-USD" in account["market_history"]
    assert "AAPL" not in account["market_history"]


@pytest.mark.unit
def test_save_paper_account_uses_unique_temp_files(monkeypatch, tmp_path):
    monkeypatch.setattr("frontend.server._workbench_user_root", lambda _user_id: tmp_path)

    _save_paper_account("kim", {"initial_cash": 100000.0, "cash": 100000.0})
    _save_paper_account("kim", {"initial_cash": 100000.0, "cash": 99999.0})

    assert _paper_account_file("kim").exists()
    assert not list(tmp_path.glob("paper_account.json.*.tmp"))


@pytest.mark.unit
def test_live_market_quote_falls_back_to_daily_quote(monkeypatch):
    monkeypatch.setattr(
        "frontend.server._intraday_market_quote",
        lambda _ticker, _asset_type: (_ for _ in ()).throw(RuntimeError("intraday down")),
    )
    monkeypatch.setattr(
        "frontend.server._latest_market_quote",
        lambda ticker, asset_type: {"ticker": ticker, "asset_type": asset_type, "price": 101.0},
    )

    assert _live_market_quote("AAPL", "stock")["price"] == 101.0


@pytest.mark.unit
def test_mark_paper_account_uses_live_quote_for_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr("frontend.server._workbench_user_root", lambda _user_id: tmp_path)
    monkeypatch.setattr(
        "frontend.server._live_market_quote",
        lambda ticker, asset_type: {
            "ticker": ticker,
            "market_ticker": ticker,
            "asset_type": asset_type,
            "price": 326.7,
            "as_of": "2026-07-21T03:59:00+08:00",
            "history": [],
        },
    )

    payload = _mark_paper_account("kim", ticker="AAPL", asset_type="stock")

    assert payload["quote"]["as_of"] == "2026-07-21T03:59:00+08:00"
    assert payload["snapshots"][-1]["trade_date"].startswith("2026-07-21")
