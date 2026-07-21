import pandas as pd
import pytest

from frontend import server
from tradingagents.backtesting.engine import BacktestResult
from tradingagents.backtesting.metrics import compute_performance_metrics
from tradingagents.backtesting.engine import BacktestTrade
from tradingagents.papertrading import (
    PaperEpisode,
    PaperEpisodeLedger,
    PaperTradingRunner,
    quote_staleness_days,
    summarize_episodes,
)


def _price_loader(_ticker, _start_date, _end_date):
    return pd.DataFrame(
        {"Close": [100.0, 105.0, 110.0]},
        index=pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-03"]),
    )


def _final_state(action="buy", target_position_size=0.10):
    return {
        "final_trade_decision": "**Rating**: Buy",
        "execution_plan": {
            "action": action,
            "target_position_size": target_position_size,
            "risk_gate_approved": True,
        },
    }


@pytest.mark.unit
def test_episode_ledger_records_paper_result_and_upserts(tmp_path):
    result = PaperTradingRunner(_price_loader).run_from_final_state(
        "NVDA",
        "2026-05-01",
        _final_state(),
        holding_days=2,
        initial_capital=100000.0,
    )
    ledger = PaperEpisodeLedger(tmp_path / "paper_episodes.json")

    book = ledger.append_from_paper_result(
        result,
        "historical_replay",
        source_run_id="run-123",
        thesis="AI demand remains resilient.",
        confidence=0.8,
        benchmark="SPY",
        initial_capital=100000.0,
        market_vendor="test_vendor",
        market_as_of="2026-05-03",
        reference_date="2026-05-05",
    )
    book = ledger.append_from_paper_result(
        result,
        "historical_replay",
        source_run_id="run-123",
        confidence=0.8,
        initial_capital=100000.0,
        market_vendor="test_vendor",
        market_as_of="2026-05-03",
        reference_date="2026-05-05",
    )

    assert len(book.episodes) == 1
    episode = book.episodes[0]
    assert episode.ticker == "NVDA"
    assert episode.mode == "historical_replay"
    assert episode.simulation_type == "backtest"
    assert episode.status == "completed"
    assert episode.final_return == pytest.approx(0.01)
    assert episode.market_data.is_stale is True
    assert episode.market_data.staleness_days == 2

    summary = ledger.summary()
    assert summary["total_episodes"] == 1
    assert summary["mode_counts"] == {"historical_replay": 1}
    assert summary["simulation_type_counts"] == {"backtest": 1}
    assert summary["facets"]["rating"]["Buy"]["win_rate"] == pytest.approx(1.0)


@pytest.mark.unit
def test_episode_summary_facets_split_modes_and_actions():
    buy = PaperEpisode(
        episode_id="buy-1",
        mode="live",
        ticker="NVDA",
        rating="Buy",
        action="buy",
        resolved=True,
        final_return=0.05,
        confidence=0.7,
        target_position_size=0.1,
    )
    hold = PaperEpisode(
        episode_id="hold-1",
        mode="historical_replay",
        ticker="AAPL",
        rating="Hold",
        action="hold",
        resolved=True,
        final_return=0.0,
        confidence=0.4,
        target_position_size=0.0,
        status="no_trade",
    )

    summary = summarize_episodes([buy, hold])

    assert summary["total_episodes"] == 2
    assert summary["status_counts"]["tracking"] == 1
    assert summary["status_counts"]["no_trade"] == 1
    assert summary["simulation_type_counts"] == {"paper_trade": 1, "backtest": 1}
    assert summary["facets"]["action"]["buy"]["average_return"] == pytest.approx(0.05)
    assert summary["facets"]["mode"]["historical_replay"]["observed_count"] == 1
    assert summary["facets"]["simulation_type"]["backtest"]["observed_count"] == 1


@pytest.mark.unit
def test_episode_can_be_created_from_backtest_trade():
    trade = BacktestTrade(
        ticker="NVDA",
        trade_date="2026-05-01",
        asset_type="stock",
        rating="Buy",
        action="buy",
        target_position_size=0.10,
        risk_gate_approved=True,
        raw_return=0.20,
        executed_return=0.02,
        alpha_return=0.10,
        executed_alpha_return=0.01,
        holding_days=5,
        benchmark="SPY",
        confidence=0.9,
        initial_capital=100000.0,
        ending_capital=102000.0,
    )

    episode = PaperEpisode.from_backtest_trade(trade, source_run_id="run-456")

    assert episode.mode == "backtest"
    assert episode.simulation_type == "backtest"
    assert episode.final_return == pytest.approx(0.02)
    assert episode.alpha_return == pytest.approx(0.01)
    assert episode.final_equity == pytest.approx(102000.0)
    assert episode.benchmark == "SPY"


@pytest.mark.unit
def test_quote_staleness_days_uses_date_only_values():
    assert quote_staleness_days("2026-05-01T12:00:00Z", "2026-05-03") == 2
    assert quote_staleness_days("", "2026-05-03") is None


@pytest.mark.unit
def test_paper_runner_extends_missing_future_with_simulated_prices():
    result = PaperTradingRunner(_price_loader).run_from_final_state(
        "NVDA",
        "2026-05-01",
        _final_state(),
        holding_days=20,
        initial_capital=100000.0,
    )

    assert result.resolved is True
    assert result.holding_days == 20
    assert len(result.snapshots) == 21
    assert [snapshot.price_source for snapshot in result.snapshots[:3]] == ["real", "real", "real"]
    assert all(snapshot.price_source == "simulated" for snapshot in result.snapshots[3:])
    assert "simulated price points" in result.reason
    assert result.simulation["price_source_counts"] == {"real": 3, "simulated": 18}
    assert result.simulation["scenario_summary"]["paths"] == 200
    assert set(result.simulation["scenario_summary"]["quantiles"]) == {"p10", "p50", "p90"}


@pytest.mark.unit
def test_paper_runner_accepts_simulation_controls():
    result = PaperTradingRunner(_price_loader).run_from_final_state(
        "NVDA",
        "2026-05-01",
        _final_state(),
        holding_days=10,
        initial_capital=100000.0,
        simulation_options={
            "scenario": "stress",
            "drift": -0.02,
            "volatility": 0.04,
            "seed": "case-a",
            "num_paths": 25,
        },
    )

    assert result.simulation["scenario"] == "stress"
    assert result.simulation["drift"] == pytest.approx(-0.02)
    assert result.simulation["volatility"] == pytest.approx(0.04)
    assert result.simulation["num_paths"] == 25
    assert result.simulation["scenario_summary"]["paths"] == 25


@pytest.mark.unit
def test_paper_runner_records_scenario_quantile_series():
    final_state = _final_state()
    final_state["execution_plan"]["entry_price"] = 100.0

    result = PaperTradingRunner(lambda _ticker, _start_date, _end_date: pd.DataFrame()).run_from_final_state(
        "NVDA",
        "2026-07-21",
        final_state,
        holding_days=5,
        initial_capital=100000.0,
        simulation_options={"scenario": "bear", "seed": "stable", "num_paths": 30},
    )

    summary = result.simulation["scenario_summary"]
    assert result.resolved is True
    assert result.simulation["scenario"] == "bear"
    assert set(summary["scenarios"]) == {"base", "bull", "bear", "stress"}
    assert summary["selected_scenario"] == "bear"
    assert len(summary["series"]) == 6
    assert {"p10", "p50", "p90", "return_p10", "return_p50", "return_p90"} <= set(summary["series"][0])
    assert summary["scenarios"]["bull"]["quantiles"]["p50"] >= summary["scenarios"]["stress"]["quantiles"]["p50"]


@pytest.mark.unit
def test_episode_public_comparison_reconciles_simulation_with_real_prices():
    final_state = _final_state()
    final_state["execution_plan"]["entry_price"] = 100.0
    result = PaperTradingRunner(lambda _ticker, _start_date, _end_date: pd.DataFrame()).run_from_final_state(
        "NVDA",
        "2026-07-21",
        final_state,
        holding_days=3,
        initial_capital=100000.0,
        simulation_options={"seed": "compare"},
    )
    episode = PaperEpisode.from_paper_result(
        result,
        "forward_test",
        source_run_id="run-compare",
        tags={"simulation_summary": result.simulation["scenario_summary"]},
    )
    quote = {
        "price": 104.0,
        "as_of": "2026-07-23",
        "history": [
            {"date": "2026-07-21", "close": 100.0},
            {"date": "2026-07-22", "close": 103.0},
            {"date": "2026-07-23", "close": 104.0},
        ],
    }

    comparison = server._episode_public_comparison(episode, quote)

    assert len(comparison["series"]) == len(comparison["forecast_series"])
    assert comparison["series"][1]["covered_by_real"] is True
    assert comparison["forecast_series"][1]["price_source"] == "simulated"
    assert comparison["actual_return"] == pytest.approx(0.004)
    assert comparison["reconciliation"]["covered_points"] >= 2
    assert comparison["reconciliation"]["latest"]["covered_by_real"] is True
    assert comparison["validity"] in {"valid", "drifting", "invalidated"}


@pytest.mark.unit
def test_episode_public_comparison_keeps_full_forecast_when_real_history_is_short():
    final_state = _final_state()
    final_state["execution_plan"]["entry_price"] = 100.0
    result = PaperTradingRunner(lambda _ticker, _start_date, _end_date: pd.DataFrame()).run_from_final_state(
        "NVDA",
        "2026-07-01",
        final_state,
        holding_days=40,
        initial_capital=100000.0,
        simulation_options={"seed": "short-real"},
    )
    episode = PaperEpisode.from_paper_result(result, "forward_test")
    quote = {
        "price": 105.0,
        "as_of": "2026-08-10",
        "history": [
            {"date": "2026-08-09", "close": 104.0},
            {"date": "2026-08-10", "close": 105.0},
        ],
    }

    comparison = server._episode_public_comparison(episode, quote)

    assert len(comparison["forecast_series"]) == 41
    assert len(comparison["actual_series"]) == 2
    assert len(comparison["series"]) == 41
    assert comparison["series"][-1]["covered_by_real"] is True


@pytest.mark.unit
def test_workbench_records_paper_episode_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    result = PaperTradingRunner(_price_loader).run_from_final_state(
        "NVDA",
        "2026-05-01",
        _final_state(),
        holding_days=2,
        initial_capital=100000.0,
    )

    episode = server._record_paper_result_episode(
        "kim",
        result,
        "historical_replay",
        source_run_id="run-789",
        confidence=0.75,
        initial_capital=100000.0,
    )
    payload = server._paper_episodes_payload("kim")

    assert (tmp_path / "paper_episodes.json").exists()
    assert payload["count"] == 1
    assert payload["items"][0]["episode_id"] == episode.episode_id
    assert payload["summary"]["mode_counts"]["historical_replay"] == 1
    assert payload["summary"]["simulation_type_counts"]["backtest"] == 1
    assert payload["items"][0]["simulation_type"] == "backtest"
    assert payload["summary"]["facets"]["ticker"]["NVDA"]["win_rate"] == pytest.approx(1.0)


@pytest.mark.unit
def test_workbench_records_backtest_episodes(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    trade = BacktestTrade(
        ticker="NVDA",
        trade_date="2026-05-01",
        asset_type="stock",
        rating="Buy",
        action="buy",
        target_position_size=0.10,
        risk_gate_approved=True,
        raw_return=0.20,
        executed_return=0.02,
        alpha_return=0.10,
        executed_alpha_return=0.01,
        holding_days=5,
        benchmark="SPY",
        confidence=0.9,
        initial_capital=100000.0,
        ending_capital=102000.0,
    )
    result = BacktestResult(
        trades=[trade],
        metrics=compute_performance_metrics([trade.executed_return], [trade.executed_alpha_return]),
    )

    episodes = server._record_backtest_result_episodes(
        "kim",
        result,
        source_run_id="run-backtest",
    )
    payload = server._paper_episodes_payload("kim")

    assert len(episodes) == 1
    assert payload["summary"]["mode_counts"]["backtest"] == 1
    assert payload["summary"]["simulation_type_counts"]["backtest"] == 1
    assert payload["items"][0]["final_return"] == pytest.approx(0.02)


@pytest.mark.unit
def test_workbench_manual_historical_replay_records_episode(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    monkeypatch.setattr(
        server.TradingAgentsGraph,
        "run_paper_trade_from_final_state",
        lambda _graph, ticker, trade_date, final_state, **kwargs: PaperTradingRunner(_price_loader).run_from_final_state(
            ticker,
            trade_date,
            final_state,
            holding_days=kwargs.get("holding_days", 2),
            initial_capital=kwargs.get("initial_capital", 100000.0),
            asset_type=kwargs.get("asset_type", "stock"),
            simulation_options=kwargs.get("simulation_options"),
        ),
    )

    payload = server._run_manual_paper_replay(
        "kim",
        {
            "ticker": "NVDA",
            "asset_type": "stock",
            "trade_date": "2026-05-01",
            "action": "buy",
            "target_position_size": 0.10,
            "horizon_days": 2,
            "initial_cash": 100000.0,
            "thesis": "Manual date replay.",
        },
    )
    ledger_payload = server._paper_episodes_payload("kim")

    assert payload["ok"] is True
    assert payload["manual"] is True
    assert payload["result"]["final_return"] == pytest.approx(0.01)
    assert ledger_payload["count"] == 1
    assert ledger_payload["items"][0]["simulation_type"] == "backtest"
    assert ledger_payload["items"][0]["tags"]["entrypoint"] == "api_paper_replay_manual"


@pytest.mark.unit
def test_workbench_creates_forecast_observation_without_paper_account(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    monkeypatch.setattr(
        server,
        "_latest_market_quote",
        lambda ticker, asset_type="stock": {
            "ticker": ticker,
            "market_ticker": ticker,
            "asset_type": asset_type,
            "price": 105.0,
            "as_of": "2026-07-22",
            "change": 0.0,
            "change_percent": 0.0,
            "history": [
                {"date": "2026-07-21", "close": 100.0},
                {"date": "2026-07-22", "close": 105.0},
            ],
        },
    )

    payload = server._create_forecast_observation(
        "kim",
        {
            "ticker": "NVDA",
            "asset_type": "stock",
            "action": "buy",
            "target_position_size": 0.10,
            "horizon_days": 5,
            "entry_price": 100.0,
            "source_run_id": "run-forecast",
            "thesis": "Forward observation.",
        },
    )
    ledger_payload = server._paper_episodes_payload("kim")
    conclusions_payload = server._conclusions_payload("kim")

    assert payload["ok"] is True
    assert not (tmp_path / "paper_account.json").exists()
    assert ledger_payload["summary"]["simulation_type_counts"]["forecast"] == 1
    assert ledger_payload["items"][0]["mode"] == "forward_test"
    assert conclusions_payload["items"][0]["simulation_links"]["forecast_episode_id"] == payload["episode"]["episode_id"]
    assert conclusions_payload["items"][0]["simulations"][0]["series"][1]["strategy_return"] == pytest.approx(0.005)
    assert conclusions_payload["items"][0]["actual_return"] == pytest.approx(0.005)
    assert conclusions_payload["items"][0]["review_conclusion"]


@pytest.mark.unit
def test_workbench_forecast_observation_uses_real_history_for_past_date(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    monkeypatch.setattr(server, "_today_iso", lambda: "2026-07-21")
    monkeypatch.setattr(
        server,
        "_latest_market_quote",
        lambda ticker, asset_type="stock": {
            "ticker": ticker,
            "market_ticker": ticker,
            "asset_type": asset_type,
            "price": 110.0,
            "as_of": "2026-07-21",
            "change": 0.0,
            "change_percent": 0.0,
            "history": [
                {"date": "2026-05-01", "close": 100.0},
                {"date": "2026-05-02", "close": 105.0},
                {"date": "2026-05-03", "close": 110.0},
            ],
        },
    )
    monkeypatch.setattr(
        server.TradingAgentsGraph,
        "run_paper_trade_from_final_state",
        lambda _graph, ticker, trade_date, final_state, **kwargs: PaperTradingRunner(_price_loader).run_from_final_state(
            ticker,
            trade_date,
            final_state,
            holding_days=kwargs.get("holding_days", 2),
            initial_capital=kwargs.get("initial_capital", 100000.0),
            asset_type=kwargs.get("asset_type", "stock"),
            simulation_options=kwargs.get("simulation_options"),
        ),
    )

    payload = server._create_forecast_observation(
        "kim",
        {
            "ticker": "NVDA",
            "asset_type": "stock",
            "analysis_date": "2026-05-01",
            "action": "buy",
            "target_position_size": 0.10,
            "horizon_days": 2,
            "source_run_id": "run-past-sim",
            "thesis": "Past simulation run.",
        },
    )
    ledger_payload = server._paper_episodes_payload("kim")
    conclusions_payload = server._conclusions_payload("kim")

    assert payload["data_mode"] == "real_history"
    assert payload["episode"]["mode"] == "forward_test"
    assert payload["episode"]["simulation_type"] == "forecast"
    assert payload["episode"]["resolved"] is True
    assert payload["episode"]["final_return"] == pytest.approx(0.01)
    assert ledger_payload["summary"]["simulation_type_counts"]["forecast"] == 1
    assert conclusions_payload["items"][0]["status"] == "due_review"


@pytest.mark.unit
def test_workbench_forecast_observation_simulates_full_path_for_current_date(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_workbench_user_root", lambda _user_id: tmp_path)
    monkeypatch.setattr(server, "_today_iso", lambda: "2026-07-21")
    monkeypatch.setattr(
        server,
        "_latest_market_quote",
        lambda ticker, asset_type="stock": {
            "ticker": ticker,
            "market_ticker": ticker,
            "asset_type": asset_type,
            "price": 100.0,
            "as_of": "2026-07-21",
            "change": 0.0,
            "change_percent": 0.0,
            "history": [{"date": "2026-07-21", "close": 100.0}],
        },
    )
    monkeypatch.setattr(
        server.TradingAgentsGraph,
        "run_paper_trade_from_final_state",
        lambda _graph, ticker, trade_date, final_state, **kwargs: PaperTradingRunner(
            lambda _ticker, _start_date, _end_date: pd.DataFrame()
        ).run_from_final_state(
            ticker,
            trade_date,
            final_state,
            holding_days=kwargs.get("holding_days", 20),
            initial_capital=kwargs.get("initial_capital", 100000.0),
            asset_type=kwargs.get("asset_type", "stock"),
            simulation_options=kwargs.get("simulation_options"),
        ),
    )

    payload = server._create_forecast_observation(
        "kim",
        {
            "ticker": "NVDA",
            "asset_type": "stock",
            "analysis_date": "2026-07-21",
            "action": "buy",
            "target_position_size": 0.10,
            "horizon_days": 20,
            "source_run_id": "run-current-sim",
            "entry_price": 100.0,
            "thesis": "Current simulation run.",
        },
    )

    assert payload["ok"] is True
    assert payload["data_mode"] == "simulated_path"
    assert payload["episode"]["resolved"] is True
    assert payload["episode"]["horizon_days"] == 20
    assert len(payload["episode"]["snapshots"]) == 21
    assert all(snapshot["price_source"] == "simulated" for snapshot in payload["episode"]["snapshots"])
    assert payload["episode"]["tags"]["simulation_summary"]["paths"] == 200
    assert payload["track"]["status"] == "tracking"
