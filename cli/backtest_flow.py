from __future__ import annotations

from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()


def parse_holding_days_input(raw: str) -> list[int]:
    raw = raw.replace("，", ",").replace(" ", "")
    values = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        values.append(max(1, int(token)))
    return values or [5]


def parse_initial_capital_input(raw: str) -> float:
    normalized = raw.replace(",", "").strip()
    if not normalized:
        return 1.0
    return max(0.01, float(normalized))


def display_backtest_result(result, ticker: str, trade_date: str, holding_days: int):
    console.print()
    console.print(Rule("Backtest Result", style="bold yellow"))

    if not result.trades:
        console.print(
            Panel(
                f"No backtest trade could be resolved for {ticker} on {trade_date}.\n"
                "This usually means future price data is not yet available for the requested holding window.",
                title="Backtest",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        return

    trade = result.trades[0]
    trade_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    trade_table.add_column("Field", style="cyan")
    trade_table.add_column("Value", style="green")
    trade_table.add_row("Ticker", trade.ticker)
    trade_table.add_row("Trade Date", trade.trade_date)
    trade_table.add_row("Rating", trade.rating)
    trade_table.add_row("Action", trade.action)
    trade_table.add_row("Target Position Size", f"{trade.target_position_size:.2%}")
    trade_table.add_row("Risk Gate Approved", str(trade.risk_gate_approved))
    trade_table.add_row("Holding Days", str(trade.holding_days))
    trade_table.add_row("Benchmark", trade.benchmark)
    trade_table.add_row("Initial Capital", f"{trade.initial_capital:,.2f}")
    trade_table.add_row("Ending Capital", f"{trade.ending_capital:,.2f}")
    trade_table.add_row("Raw Return", f"{trade.raw_return:.2%}")
    trade_table.add_row("Executed Return", f"{trade.executed_return:.2%}")
    trade_table.add_row("Alpha Return", f"{trade.alpha_return:.2%}")
    trade_table.add_row("Executed Alpha Return", f"{trade.executed_alpha_return:.2%}")
    trade_table.add_row("Confidence", f"{trade.confidence:.2%}")

    metrics = result.metrics
    metrics_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green")
    metrics_table.add_row("Trade Count", str(metrics.trade_count))
    metrics_table.add_row("Total Return", f"{metrics.total_return:.2%}")
    metrics_table.add_row("Average Return", f"{metrics.average_return:.2%}")
    metrics_table.add_row("Average Alpha", f"{metrics.average_alpha:.2%}")
    metrics_table.add_row("Win Rate", f"{metrics.win_rate:.2%}")
    metrics_table.add_row("Loss Rate", f"{metrics.loss_rate:.2%}")
    metrics_table.add_row("Volatility", f"{metrics.volatility:.4f}")
    metrics_table.add_row("Sharpe Ratio", f"{metrics.sharpe_ratio:.4f}")
    metrics_table.add_row("Max Drawdown", f"{metrics.max_drawdown:.2%}")

    console.print(Panel(trade_table, title=f"Scenario Backtest ({holding_days}d)", border_style="yellow"))
    console.print(Panel(metrics_table, title="Backtest Metrics", border_style="yellow"))


def save_backtest_result_to_disk(result, ticker: str, trade_date: str, holding_days: int, save_path: Path):
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / f"backtest_{ticker}_{trade_date}_{holding_days}d.md"

    lines = [
        f"# Backtest Result: {ticker}",
        "",
        f"- Trade Date: {trade_date}",
        f"- Holding Days: {holding_days}",
        "",
    ]

    if not result.trades:
        lines.extend([
            "## Outcome",
            "",
            "No backtest trade could be resolved for this scenario.",
        ])
    else:
        trade = result.trades[0]
        metrics = result.metrics
        lines.extend([
            "## Trade",
            "",
            f"- Rating: {trade.rating}",
            f"- Action: {trade.action}",
            f"- Target Position Size: {trade.target_position_size:.2%}",
            f"- Risk Gate Approved: {trade.risk_gate_approved}",
            f"- Benchmark: {trade.benchmark}",
            f"- Initial Capital: {trade.initial_capital:,.2f}",
            f"- Ending Capital: {trade.ending_capital:,.2f}",
            f"- Raw Return: {trade.raw_return:.2%}",
            f"- Executed Return: {trade.executed_return:.2%}",
            f"- Alpha Return: {trade.alpha_return:.2%}",
            f"- Executed Alpha Return: {trade.executed_alpha_return:.2%}",
            f"- Confidence: {trade.confidence:.2%}",
            "",
            "## Metrics",
            "",
            f"- Trade Count: {metrics.trade_count}",
            f"- Total Return: {metrics.total_return:.2%}",
            f"- Average Return: {metrics.average_return:.2%}",
            f"- Average Alpha: {metrics.average_alpha:.2%}",
            f"- Win Rate: {metrics.win_rate:.2%}",
            f"- Loss Rate: {metrics.loss_rate:.2%}",
            f"- Volatility: {metrics.volatility:.4f}",
            f"- Sharpe Ratio: {metrics.sharpe_ratio:.4f}",
            f"- Max Drawdown: {metrics.max_drawdown:.2%}",
        ])

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def display_backtest_summary(results: list[tuple[int, object]]):
    console.print()
    console.print(Rule("Backtest Summary", style="bold yellow"))

    summary_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    summary_table.add_column("Holding Days", style="cyan")
    summary_table.add_column("Trade Count", style="green")
    summary_table.add_column("Rating", style="yellow")
    summary_table.add_column("Action", style="yellow")
    summary_table.add_column("End Capital", style="green")
    summary_table.add_column("Executed Return", style="green")
    summary_table.add_column("Executed Alpha", style="green")
    summary_table.add_column("Win Rate", style="green")
    summary_table.add_column("Sharpe", style="green")
    summary_table.add_column("Max DD", style="green")

    for holding_days, result in results:
        if result.trades:
            trade = result.trades[0]
            metrics = result.metrics
            summary_table.add_row(
                str(holding_days),
                str(metrics.trade_count),
                trade.rating,
                trade.action,
                f"{trade.ending_capital:,.2f}",
                f"{trade.executed_return:.2%}",
                f"{trade.executed_alpha_return:.2%}",
                f"{metrics.win_rate:.2%}",
                f"{metrics.sharpe_ratio:.4f}",
                f"{metrics.max_drawdown:.2%}",
            )
        else:
            summary_table.add_row(
                str(holding_days),
                "0",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
            )

    console.print(Panel(summary_table, title="Multi-Horizon Comparison", border_style="yellow"))


def save_backtest_summary_to_disk(
    results: list[tuple[int, object]],
    ticker: str,
    trade_date: str,
    save_path: Path,
):
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / f"backtest_summary_{ticker}_{trade_date}.md"

    lines = [
        f"# Backtest Summary: {ticker}",
        "",
        f"- Trade Date: {trade_date}",
        "",
        "| Holding Days | Trade Count | Rating | Action | Ending Capital | Executed Return | Executed Alpha | Win Rate | Sharpe | Max Drawdown |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for holding_days, result in results:
        if result.trades:
            trade = result.trades[0]
            metrics = result.metrics
            lines.append(
                f"| {holding_days} | {metrics.trade_count} | {trade.rating} | {trade.action} | {trade.ending_capital:,.2f} | "
                f"{trade.executed_return:.2%} | {trade.executed_alpha_return:.2%} | "
                f"{metrics.win_rate:.2%} | {metrics.sharpe_ratio:.4f} | {metrics.max_drawdown:.2%} |"
            )
        else:
            lines.append(f"| {holding_days} | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path
