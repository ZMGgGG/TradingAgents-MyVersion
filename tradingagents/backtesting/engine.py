from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, Field

from tradingagents.agents.utils.rating import parse_rating

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
    raw_return: float
    alpha_return: float
    holding_days: int
    benchmark: str
    confidence: float = 0.0


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
            trades.append(
                BacktestTrade(
                    ticker=scenario.ticker,
                    trade_date=scenario.trade_date,
                    asset_type=scenario.asset_type,
                    rating=rating,
                    raw_return=raw_return,
                    alpha_return=alpha_return,
                    holding_days=actual_days,
                    benchmark=benchmark,
                    confidence=confidence,
                )
            )

        metrics = compute_performance_metrics(
            [trade.raw_return for trade in trades],
            [trade.alpha_return for trade in trades],
        )
        return BacktestResult(trades=trades, metrics=metrics)

    def run_from_final_states(
        self,
        scenarios: Sequence[BacktestScenario],
        final_states: Sequence[dict[str, Any]],
        holding_days: int = 5,
    ) -> BacktestResult:
        """Backtest existing analysis results without re-running the graph."""
        trades: list[BacktestTrade] = []
        for scenario, final_state in zip(scenarios, final_states):
            rating = parse_rating(final_state.get("final_trade_decision", "Hold"))
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
            trades.append(
                BacktestTrade(
                    ticker=scenario.ticker,
                    trade_date=scenario.trade_date,
                    asset_type=scenario.asset_type,
                    rating=rating,
                    raw_return=raw_return,
                    alpha_return=alpha_return,
                    holding_days=actual_days,
                    benchmark=benchmark,
                    confidence=confidence,
                )
            )

        metrics = compute_performance_metrics(
            [trade.raw_return for trade in trades],
            [trade.alpha_return for trade in trades],
        )
        return BacktestResult(trades=trades, metrics=metrics)
