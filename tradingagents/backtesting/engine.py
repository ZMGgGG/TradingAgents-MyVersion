from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, Field

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.decisioning.execution_policy import rating_to_execution_action

from .metrics import PerformanceMetrics, compute_performance_metrics


class BacktestScenario(BaseModel):
    ticker: str
    trade_date: str
    asset_type: str = "stock"


class BacktestTrade(BaseModel):
    ticker: str
    trade_date: str
    asset_type: str
    rating: str
    action: str
    target_position_size: float
    risk_gate_approved: bool
    raw_return: float
    executed_return: float
    alpha_return: float
    executed_alpha_return: float
    holding_days: int
    benchmark: str
    confidence: float = 0.0
    initial_capital: float = 1.0
    ending_capital: float = 1.0


class BacktestResult(BaseModel):
    trades: list[BacktestTrade] = Field(default_factory=list)
    metrics: PerformanceMetrics


class BatchBacktester:
    """Run a basic batch backtest through an existing TradingAgentsGraph."""

    def __init__(self, graph: Any):
        self.graph = graph

    def run(
        self,
        scenarios: Sequence[BacktestScenario],
        holding_days: int = 5,
        initial_capital: float = 1.0,
    ) -> BacktestResult:
        """Execute a batch backtest over multiple ticker-date scenarios."""
        trades: list[BacktestTrade] = []
        for scenario in scenarios:
            final_state, decision = self.graph.propagate(
                scenario.ticker,
                scenario.trade_date,
                asset_type=scenario.asset_type,
            )
            rating = parse_rating(final_state.get("final_trade_decision", decision))
            execution_plan = final_state.get("execution_plan", {})
            benchmark = self.graph._resolve_benchmark(scenario.ticker)
            raw_return, alpha_return, actual_days = self.graph._fetch_returns(
                scenario.ticker,
                scenario.trade_date,
                holding_days=holding_days,
                benchmark=benchmark,
            )
            if raw_return is None or alpha_return is None or actual_days is None:
                continue
            confidence = float(
                final_state.get("investment_debate_state", {}).get("signal_confidence", 0.0)
            )
            action, target_position_size, risk_gate_approved = self._resolve_execution_inputs(
                rating,
                execution_plan,
            )
            executed_return, executed_alpha_return = self._apply_execution_plan(
                action,
                target_position_size,
                risk_gate_approved,
                raw_return,
                alpha_return,
            )
            trades.append(
                BacktestTrade(
                    ticker=scenario.ticker,
                    trade_date=scenario.trade_date,
                    asset_type=scenario.asset_type,
                    rating=rating,
                    action=action,
                    target_position_size=target_position_size,
                    risk_gate_approved=risk_gate_approved,
                    raw_return=raw_return,
                    executed_return=executed_return,
                    alpha_return=alpha_return,
                    executed_alpha_return=executed_alpha_return,
                    holding_days=actual_days,
                    benchmark=benchmark,
                    confidence=confidence,
                    initial_capital=initial_capital,
                    ending_capital=initial_capital * (1.0 + executed_return),
                )
            )

        metrics = compute_performance_metrics(
            [trade.executed_return for trade in trades],
            [trade.executed_alpha_return for trade in trades],
        )
        return BacktestResult(trades=trades, metrics=metrics)

    def run_from_final_states(
        self,
        scenarios: Sequence[BacktestScenario],
        final_states: Sequence[dict[str, Any]],
        holding_days: int = 5,
        initial_capital: float = 1.0,
    ) -> BacktestResult:
        """Backtest existing analysis results without re-running the graph."""
        trades: list[BacktestTrade] = []
        for scenario, final_state in zip(scenarios, final_states):
            rating = parse_rating(final_state.get("final_trade_decision", "Hold"))
            execution_plan = final_state.get("execution_plan", {})
            benchmark = self.graph._resolve_benchmark(scenario.ticker)
            raw_return, alpha_return, actual_days = self.graph._fetch_returns(
                scenario.ticker,
                scenario.trade_date,
                holding_days=holding_days,
                benchmark=benchmark,
            )
            if raw_return is None or alpha_return is None or actual_days is None:
                continue
            confidence = float(
                final_state.get("investment_debate_state", {}).get("signal_confidence", 0.0)
            )
            action, target_position_size, risk_gate_approved = self._resolve_execution_inputs(
                rating,
                execution_plan,
            )
            executed_return, executed_alpha_return = self._apply_execution_plan(
                action,
                target_position_size,
                risk_gate_approved,
                raw_return,
                alpha_return,
            )
            trades.append(
                BacktestTrade(
                    ticker=scenario.ticker,
                    trade_date=scenario.trade_date,
                    asset_type=scenario.asset_type,
                    rating=rating,
                    action=action,
                    target_position_size=target_position_size,
                    risk_gate_approved=risk_gate_approved,
                    raw_return=raw_return,
                    executed_return=executed_return,
                    alpha_return=alpha_return,
                    executed_alpha_return=executed_alpha_return,
                    holding_days=actual_days,
                    benchmark=benchmark,
                    confidence=confidence,
                    initial_capital=initial_capital,
                    ending_capital=initial_capital * (1.0 + executed_return),
                )
            )

        metrics = compute_performance_metrics(
            [trade.executed_return for trade in trades],
            [trade.executed_alpha_return for trade in trades],
        )
        return BacktestResult(trades=trades, metrics=metrics)

    def _resolve_execution_inputs(
        self,
        rating: str,
        execution_plan: dict[str, Any],
    ) -> tuple[str, float, bool]:
        action = rating_to_execution_action(execution_plan.get("action", rating))
        target_position_size = float(execution_plan.get("target_position_size", 0.0))
        risk_gate_approved = bool(execution_plan.get("risk_gate_approved", True))
        return action, target_position_size, risk_gate_approved

    def _apply_execution_plan(
        self,
        action: str,
        target_position_size: float,
        risk_gate_approved: bool,
        raw_return: float,
        alpha_return: float,
    ) -> tuple[float, float]:
        if not risk_gate_approved:
            return 0.0, 0.0
        size = max(0.0, min(1.0, target_position_size))
        if action == "hold":
            if size <= 0.0:
                return 0.0, 0.0
            return raw_return * size, alpha_return * size
        if action in {"buy", "overweight"}:
            return raw_return * size, alpha_return * size
        if action == "underweight":
            return raw_return * size * 0.5, alpha_return * size * 0.5
        if action == "sell":
            return -raw_return * size, -alpha_return * size
        return 0.0, 0.0
