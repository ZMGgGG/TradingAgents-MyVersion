from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.decisioning.execution_policy import rating_to_execution_action

from .broker import PaperBroker
from .models import PaperOrder, PaperTradingResult

PriceLoader = Callable[[str, str, str], pd.DataFrame]

SCENARIO_DRIFT_BIASES = {
    "base": 0.0,
    "bull": 0.01,
    "bear": -0.01,
    "stress": -0.025,
}
SCENARIO_ORDER = ["base", "bull", "bear", "stress"]


def build_order_from_final_state(
    ticker: str,
    trade_date: str,
    final_state: dict[str, Any],
    asset_type: str = "stock",
) -> PaperOrder:
    rating = parse_rating(final_state.get("final_trade_decision", "Hold"))
    execution_plan = final_state.get("execution_plan", {}) or {}
    action = rating_to_execution_action(execution_plan.get("action", rating))
    return PaperOrder(
        ticker=ticker,
        trade_date=trade_date,
        asset_type=asset_type,
        rating=rating,
        action=action,
        target_position_size=float(execution_plan.get("target_position_size", 0.0)),
        risk_gate_approved=bool(execution_plan.get("risk_gate_approved", True)),
    )


class PaperTradingRunner:
    """Apply an existing TradingAgents conclusion to a local simulated account."""

    def __init__(self, price_loader: PriceLoader):
        self.price_loader = price_loader

    @classmethod
    def from_graph(cls, graph: Any) -> "PaperTradingRunner":
        return cls(graph._load_price_history_for_returns)

    def run_from_final_state(
        self,
        ticker: str,
        trade_date: str,
        final_state: dict[str, Any],
        holding_days: int = 5,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0,
        slippage_rate: float = 0.0,
        asset_type: str = "stock",
        simulation_options: dict[str, Any] | None = None,
    ) -> PaperTradingResult:
        holding_days = max(1, int(holding_days))
        simulation_config = self._simulation_config(asset_type, simulation_options)
        order = build_order_from_final_state(ticker, trade_date, final_state, asset_type=asset_type)
        entry_price_override = self._entry_price_override(final_state)
        history = self._load_history(ticker, trade_date, holding_days, entry_price=entry_price_override)
        if history.empty:
            return PaperTradingResult(
                ticker=ticker,
                trade_date=trade_date,
                holding_days=holding_days,
                resolved=False,
                reason="price data unavailable",
                order=order,
                simulation=simulation_config,
            )
        history = self._extend_with_simulated_prices(
            history,
            ticker=ticker,
            trade_date=trade_date,
            holding_days=holding_days,
            asset_type=asset_type,
            simulation_config=simulation_config,
        )

        broker = PaperBroker(
            initial_cash=initial_capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        entry_price = float(history["Close"].iloc[0])
        broker.submit_order(order, entry_price)

        snapshots = []
        price_sources = (
            history["price_source"].tolist()
            if "price_source" in history.columns
            else ["real"] * len(history)
        )
        for idx in range(holding_days + 1):
            row_date = self._date_label(history.index[idx], fallback=trade_date)
            price = float(history["Close"].iloc[idx])
            snapshot = broker.snapshot(row_date, {ticker: price})
            snapshot.price_source = str(price_sources[idx] or "real")
            snapshots.append(snapshot)

        simulated_days = len([snapshot for snapshot in snapshots if snapshot.price_source == "simulated"])
        real_days = len(snapshots) - simulated_days
        simulation_meta = {
            **simulation_config,
            "real_price_points": real_days,
            "simulated_price_points": simulated_days,
            "price_source_counts": {
                "real": real_days,
                "simulated": simulated_days,
            },
            "scenario_summary": self._scenario_summary(
                history,
                order=order,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate,
                ticker=ticker,
                trade_date=trade_date,
                holding_days=holding_days,
                real_points=real_days,
                asset_type=asset_type,
                simulation_config=simulation_config,
            ),
        }
        simulation_meta["scenarios"] = simulation_meta["scenario_summary"].get("scenarios", {})

        return PaperTradingResult(
            ticker=ticker,
            trade_date=trade_date,
            holding_days=holding_days,
            resolved=True,
            reason=(
                f"completed with {real_days} real price points and {simulated_days} simulated price points"
                if simulated_days
                else ""
            ),
            order=order,
            fills=list(broker.fills),
            snapshots=snapshots,
            simulation=simulation_meta,
        )

    def _load_history(
        self,
        ticker: str,
        trade_date: str,
        holding_days: int,
        entry_price: float | None = None,
    ) -> pd.DataFrame:
        start = datetime.strptime(trade_date, "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 7)
        history = self.price_loader(ticker, trade_date, end.strftime("%Y-%m-%d"))
        if not isinstance(history, pd.DataFrame) or history.empty or "Close" not in history.columns:
            if entry_price and entry_price > 0:
                return pd.DataFrame(
                    {"Close": [float(entry_price)], "price_source": ["simulated"]},
                    index=pd.to_datetime([trade_date]),
                )
            return pd.DataFrame()
        normalized = history.copy()
        normalized["Close"] = pd.to_numeric(normalized["Close"], errors="coerce")
        normalized = normalized.dropna(subset=["Close"]).sort_index()
        normalized = normalized[normalized.index >= pd.to_datetime(start)]
        if normalized.empty:
            if entry_price and entry_price > 0:
                return pd.DataFrame(
                    {"Close": [float(entry_price)], "price_source": ["simulated"]},
                    index=pd.to_datetime([trade_date]),
                )
            return pd.DataFrame()
        normalized["price_source"] = "real"
        if entry_price and entry_price > 0:
            normalized.iloc[0, normalized.columns.get_loc("Close")] = float(entry_price)
        return normalized

    def _extend_with_simulated_prices(
        self,
        history: pd.DataFrame,
        *,
        ticker: str,
        trade_date: str,
        holding_days: int,
        asset_type: str,
        simulation_config: dict[str, Any],
    ) -> pd.DataFrame:
        target_points = holding_days + 1
        if len(history) >= target_points:
            return history.iloc[:target_points].copy()

        extended = history.copy()
        if "price_source" not in extended.columns:
            extended["price_source"] = "real"
        drift, volatility = self._resolved_drift_volatility(extended, asset_type, simulation_config)
        seed_text = f"{ticker}|{trade_date}|{holding_days}|{float(extended['Close'].iloc[-1]):.8f}|{simulation_config['scenario']}|{simulation_config['seed']}"
        generator = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16))
        current_date = pd.to_datetime(extended.index[-1])
        current_price = float(extended["Close"].iloc[-1])
        rows = []
        while len(extended) + len(rows) < target_points:
            current_date = current_date + timedelta(days=1)
            daily_return = generator.gauss(drift, volatility)
            daily_return = max(-0.35, min(0.35, daily_return))
            current_price = max(0.000001, current_price * (1.0 + daily_return))
            rows.append(
                pd.DataFrame(
                    {"Close": [current_price], "price_source": ["simulated"]},
                    index=pd.to_datetime([current_date.date().isoformat()]),
                )
            )
        if rows:
            extended = pd.concat([extended, *rows])
        return extended.iloc[:target_points].copy()

    def _simulation_config(self, asset_type: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = dict(options or {})
        scenario = str(options.get("scenario") or "base").strip().lower()
        if scenario == "neutral":
            scenario = "base"
        scenario_bias = SCENARIO_DRIFT_BIASES.get(scenario, 0.0)
        default_volatility = 0.03 if asset_type == "crypto" else 0.015
        drift_value = self._float_option(options.get("drift"))
        volatility_value = self._float_option(options.get("volatility"))
        if volatility_value is not None and volatility_value > 1:
            volatility_value = volatility_value / 100.0
        num_paths = int(self._float_option(options.get("num_paths")) or 200)
        num_paths = max(1, min(1000, num_paths))
        return {
            "scenario": scenario,
            "drift": drift_value if drift_value is not None else scenario_bias,
            "drift_source": "manual" if drift_value is not None else "history",
            "volatility": max(0.0, volatility_value) if volatility_value is not None else default_volatility,
            "volatility_source": "manual" if volatility_value is not None else "history",
            "seed": str(options.get("seed") or ""),
            "num_paths": num_paths,
        }

    def _scenario_summary(
        self,
        history: pd.DataFrame,
        *,
        order: PaperOrder,
        initial_capital: float,
        commission_rate: float,
        slippage_rate: float,
        ticker: str,
        trade_date: str,
        holding_days: int,
        real_points: int,
        asset_type: str,
        simulation_config: dict[str, Any],
    ) -> dict[str, Any]:
        anchor_points = max(1, min(real_points or 1, len(history), holding_days + 1))
        simulated_needed = max(0, holding_days + 1 - anchor_points)
        base_drift, volatility = self._resolved_drift_volatility(history.iloc[:anchor_points], asset_type, simulation_config)
        selected_scenario = str(simulation_config.get("scenario") or "base")
        scenario_summaries = {}
        for scenario in SCENARIO_ORDER:
            drift = self._scenario_drift(scenario, base_drift, simulation_config)
            scenario_config = {**simulation_config, "scenario": scenario, "drift": drift, "volatility": volatility}
            scenario_summaries[scenario] = self._quantile_summary_for_scenario(
                history.iloc[:anchor_points],
                order=order,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate,
                ticker=ticker,
                trade_date=trade_date,
                holding_days=holding_days,
                simulated_needed=simulated_needed,
                real_points=real_points,
                simulation_config=scenario_config,
            )
        selected = scenario_summaries.get(selected_scenario) or scenario_summaries["base"]
        return {
            **selected,
            "selected_scenario": selected_scenario,
            "scenarios": scenario_summaries,
        }

    def _quantile_summary_for_scenario(
        self,
        history_prefix: pd.DataFrame,
        *,
        order: PaperOrder,
        initial_capital: float,
        commission_rate: float,
        slippage_rate: float,
        ticker: str,
        trade_date: str,
        holding_days: int,
        simulated_needed: int,
        real_points: int,
        simulation_config: dict[str, Any],
    ) -> dict[str, Any]:
        start_price = float(history_prefix["Close"].iloc[-1])
        drift = float(simulation_config.get("drift") or 0.0)
        volatility = float(simulation_config.get("volatility") or 0.0)
        seed_text = (
            f"summary|{ticker}|{trade_date}|{holding_days}|{start_price:.8f}|"
            f"{simulation_config.get('scenario')}|{simulation_config.get('seed')}"
        )
        generator = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16))
        paths: list[list[float]] = []
        final_returns = []
        num_paths = int(simulation_config.get("num_paths") or 1)
        for _ in range(num_paths):
            price = start_price
            path_prices = [float(value) for value in history_prefix["Close"].tolist()]
            for _day in range(simulated_needed):
                daily_return = generator.gauss(drift, volatility)
                daily_return = max(-0.35, min(0.35, daily_return))
                price = max(0.000001, price * (1.0 + daily_return))
                path_prices.append(price)
            path_prices = path_prices[: holding_days + 1]
            paths.append(path_prices)
            path_history = pd.DataFrame(
                {"Close": path_prices},
                index=self._path_index(history_prefix, len(path_prices)),
            )
            final_returns.append(
                self._run_equity_for_history(
                    path_history,
                    order=order,
                    initial_capital=initial_capital,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    ticker=ticker,
                )
            )
        final_returns = sorted(final_returns)
        return {
            "paths": len(final_returns),
            "quantiles": {
                "p10": self._quantile(final_returns, 0.10),
                "p50": self._quantile(final_returns, 0.50),
                "p90": self._quantile(final_returns, 0.90),
            },
            "series": self._quantile_series(
                paths,
                history_prefix,
                order=order,
                real_points=real_points,
            ),
        }

    def _path_index(self, history_prefix: pd.DataFrame, path_length: int) -> pd.DatetimeIndex:
        dates = [pd.to_datetime(value) for value in history_prefix.index[:path_length]]
        current_date = dates[-1]
        while len(dates) < path_length:
            current_date = current_date + timedelta(days=1)
            dates.append(pd.to_datetime(current_date.date().isoformat()))
        return pd.to_datetime(dates)

    def _quantile_series(
        self,
        paths: list[list[float]],
        history_prefix: pd.DataFrame,
        *,
        order: PaperOrder,
        real_points: int,
    ) -> list[dict[str, Any]]:
        if not paths:
            return []
        dates = self._path_index(history_prefix, len(paths[0]))
        rows = []
        for index, row_date in enumerate(dates):
            prices = sorted(path[index] for path in paths if index < len(path))
            p10 = self._quantile(prices, 0.10)
            p50 = self._quantile(prices, 0.50)
            p90 = self._quantile(prices, 0.90)
            base_price = float(history_prefix["Close"].iloc[0])
            rows.append(
                {
                    "date": self._date_label(row_date, fallback=order.trade_date),
                    "price_source": "real" if index < real_points else "simulated",
                    "p10": p10,
                    "p50": p50,
                    "p90": p90,
                    "return_p10": self._strategy_return_for_price(order, base_price, p10),
                    "return_p50": self._strategy_return_for_price(order, base_price, p50),
                    "return_p90": self._strategy_return_for_price(order, base_price, p90),
                }
            )
        return rows

    def _strategy_return_for_price(self, order: PaperOrder, entry_price: float, price: float | None) -> float:
        if not entry_price or price is None:
            return 0.0
        asset_return = (float(price) / entry_price) - 1.0
        size = max(0.0, min(1.0, float(order.target_position_size or 0.0)))
        if str(order.action).lower() in {"sell", "underweight", "short", "strong_sell", "reduce"}:
            return -size * asset_return
        if str(order.action).lower() in {"buy", "overweight", "long", "strong_buy", "accumulate"}:
            return size * asset_return
        return 0.0

    def _resolved_drift_volatility(
        self,
        history: pd.DataFrame,
        asset_type: str,
        simulation_config: dict[str, Any],
    ) -> tuple[float, float]:
        returns = history["Close"].pct_change().dropna() if "Close" in history.columns else pd.Series(dtype="float64")
        drift = float(simulation_config.get("drift") or 0.0)
        if simulation_config.get("drift_source") == "history" and len(returns) >= 2:
            drift = float(returns.mean())
        volatility = float(simulation_config.get("volatility") or 0.0)
        if simulation_config.get("volatility_source") == "history" and len(returns) >= 2:
            volatility = float(returns.std())
        if not volatility or pd.isna(volatility):
            volatility = 0.03 if asset_type == "crypto" else 0.015
        return max(-0.03, min(0.03, drift)), max(0.002, min(0.12, volatility))

    def _scenario_drift(self, scenario: str, base_drift: float, simulation_config: dict[str, Any]) -> float:
        selected = str(simulation_config.get("scenario") or "base")
        selected_bias = SCENARIO_DRIFT_BIASES.get(selected, 0.0)
        scenario_bias = SCENARIO_DRIFT_BIASES.get(scenario, 0.0)
        if simulation_config.get("drift_source") == "manual":
            drift = base_drift + scenario_bias - selected_bias
        else:
            drift = base_drift + scenario_bias
        return max(-0.03, min(0.03, drift))

    def _run_equity_for_history(
        self,
        history: pd.DataFrame,
        *,
        order: PaperOrder,
        initial_capital: float,
        commission_rate: float,
        slippage_rate: float,
        ticker: str,
    ) -> float:
        broker = PaperBroker(
            initial_cash=initial_capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        broker.submit_order(order, float(history["Close"].iloc[0]))
        final_snapshot = broker.snapshot(self._date_label(history.index[-1], fallback=order.trade_date), {ticker: float(history["Close"].iloc[-1])})
        return final_snapshot.total_return

    def _quantile(self, values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * quantile
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        weight = position - lower
        return values[lower] * (1.0 - weight) + values[upper] * weight

    def _float_option(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _entry_price_override(self, final_state: dict[str, Any]) -> float | None:
        execution_plan = final_state.get("execution_plan", {}) if isinstance(final_state, dict) else {}
        try:
            value = float((execution_plan or {}).get("entry_price") or 0.0)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _date_label(self, value: Any, fallback: str) -> str:
        if hasattr(value, "date"):
            return value.date().isoformat()
        text = str(value)
        return text[:10] if text else fallback
