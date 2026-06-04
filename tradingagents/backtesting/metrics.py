from __future__ import annotations

import math
from typing import Sequence

from pydantic import BaseModel


class PerformanceMetrics(BaseModel):
    total_return: float
    average_return: float
    average_alpha: float
    win_rate: float
    loss_rate: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int


def compute_equity_curve(returns: Sequence[float], initial_capital: float = 1.0) -> list[float]:
    """Build an equity curve from a sequence of period returns."""
    equity = initial_capital
    curve = [equity]
    for period_return in returns:
        equity *= 1.0 + period_return
        curve.append(equity)
    return curve


def compute_max_drawdown(equity_curve: Sequence[float]) -> float:
    """Compute the maximum drawdown from an equity curve."""
    peak = 0.0
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak == 0:
            continue
        drawdown = (equity - peak) / peak
        max_drawdown = min(max_drawdown, drawdown)
    return abs(max_drawdown)


def compute_performance_metrics(returns: Sequence[float], alphas: Sequence[float]) -> PerformanceMetrics:
    """Compute baseline performance metrics for a backtest run."""
    trade_count = len(returns)
    if trade_count == 0:
        return PerformanceMetrics(
            total_return=0.0,
            average_return=0.0,
            average_alpha=0.0,
            win_rate=0.0,
            loss_rate=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            trade_count=0,
        )

    total_return = math.prod(1.0 + value for value in returns) - 1.0
    average_return = sum(returns) / trade_count
    average_alpha = sum(alphas) / trade_count if alphas else 0.0
    wins = sum(1 for value in returns if value > 0)
    losses = sum(1 for value in returns if value < 0)
    win_rate = wins / trade_count
    loss_rate = losses / trade_count
    variance = sum((value - average_return) ** 2 for value in returns) / trade_count
    volatility = math.sqrt(variance)
    sharpe_ratio = average_return / volatility if volatility else 0.0
    max_drawdown = compute_max_drawdown(compute_equity_curve(returns))
    return PerformanceMetrics(
        total_return=total_return,
        average_return=average_return,
        average_alpha=average_alpha,
        win_rate=win_rate,
        loss_rate=loss_rate,
        volatility=volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        trade_count=trade_count,
    )
