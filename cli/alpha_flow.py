from __future__ import annotations

from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.console import Console

from tradingagents.alpha_mining import (
    AlphaEvaluator,
    AlphaMiningEpisode,
    AlphaMiningHistory,
    AlphaRegistry,
    QuantaAlphaMiner,
    alpha_text,
    generate_crossover_set,
    generate_mutation_set,
)
from tradingagents.backtesting.engine import BatchBacktester
from tradingagents.decisioning.execution_policy import candidate_signal_to_execution
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

console = Console()


def discover_alpha_sources(root: Path | None = None) -> list[Path]:
    base = (root or Path.cwd() / ".tradingagents" / "logs").expanduser()
    if not base.exists():
        return []
    return sorted(base.rglob("full_states_log_*.json"))


def choose_alpha_source() -> str:
    candidates = discover_alpha_sources()
    choices = [
        questionary.Choice(str(path.relative_to(Path.cwd())), value=str(path))
        for path in candidates
    ]
    choices.append(questionary.Choice("Manual path entry", value="__manual__"))

    selected = questionary.select(
        "Select an alpha source state file:",
        choices=choices,
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:cyan noinherit"),
                ("highlighted", "fg:cyan noinherit"),
                ("pointer", "fg:cyan noinherit"),
            ]
        ),
    ).ask()

    if selected == "__manual__":
        return typer.prompt(
            "Alpha source path (full_states_log_*.json or directory)",
            default="",
        ).strip()

    return selected or ""


def run_alpha_mining_for_source(
    source: Path,
    registry_path: Optional[Path] = None,
    history_path: Optional[Path] = None,
    *,
    load_alpha_state_file,
    collect_alpha_state_files,
    build_alpha_registry_entry,
    resolve_benchmark_from_default_config,
) -> tuple[Path, Path]:
    state_files = collect_alpha_state_files(source)
    if not state_files:
        raise FileNotFoundError(f"No alpha source files found in {source}")

    default_root = source if source.is_dir() else source.parent
    registry_file = registry_path or (default_root / "alpha_registry.json")
    history_file = history_path or (default_root / "alpha_history.json")

    registry = AlphaRegistry(registry_file)
    history = AlphaMiningHistory(history_file)
    evaluator = AlphaEvaluator()
    miner = QuantaAlphaMiner()
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = DEFAULT_CONFIG.copy()
    backtester = BatchBacktester(graph)
    registry.write_entries(registry.load())

    for state_file in state_files:
        if not state_file.exists():
            continue
        payload = load_alpha_state_file(state_file)
        alpha_result = miner.mine(payload)
        candidates = alpha_result.candidates or []
        mutations = [mutated for candidate in candidates for mutated in generate_mutation_set(candidate)]
        crossovers = generate_crossover_set(candidates)
        candidate_pool = candidates + mutations + crossovers

        for candidate in candidate_pool:
            alpha_result.candidates = [candidate]
            alpha_result.selected_alpha = candidate
            alpha_result.signal_score = candidate.signal_score
            alpha_result.confidence = candidate.confidence
            action, target_position_size = candidate_signal_to_execution(
                candidate.signal_score,
                candidate.confidence,
            )
            benchmark = "SPY"
            realized_return = 0.0
            realized_alpha = 0.0
            try:
                benchmark = resolve_benchmark_from_default_config(str(payload.get("company_of_interest", "")))
                raw_return, alpha_return, _actual_days = graph._fetch_returns(
                    str(payload.get("company_of_interest", "")),
                    str(payload.get("trade_date", "")),
                    holding_days=5,
                    benchmark=benchmark,
                )
                if raw_return is not None and alpha_return is not None:
                    executed_return, executed_alpha_return = backtester._apply_execution_plan(
                        action,
                        target_position_size,
                        True,
                        raw_return,
                        alpha_return,
                    )
                    realized_return = executed_return
                    realized_alpha = executed_alpha_return
            except Exception:
                pass

            alpha_result.summary = (
                f"{alpha_result.summary} realized_return={realized_return:.2%}, "
                f"realized_alpha={realized_alpha:.2%}, benchmark={benchmark}."
            )
            enriched_payload = alpha_result.model_dump()
            enriched_payload["realized_return"] = realized_return
            enriched_payload["realized_alpha"] = realized_alpha
            enriched_payload["benchmark"] = benchmark
            evaluation = evaluator.evaluate(enriched_payload)
            if evaluation.passed:
                registry.upsert(
                    build_alpha_registry_entry(
                        {
                            **payload,
                            "alpha_mining_result": {
                                **enriched_payload,
                                "evaluation_score": evaluation.score,
                            },
                        },
                        state_file,
                    )
                )
            history.append(
                AlphaMiningEpisode(
                    source=str(state_file),
                    ticker=str(payload.get("company_of_interest", "")),
                    trade_date=str(payload.get("trade_date", "")),
                    payload={
                        "alpha_result": {
                            **enriched_payload,
                            "evaluation_score": evaluation.score,
                        },
                        "evaluation": {
                            "candidate_name": evaluation.candidate_name,
                            "passed": evaluation.passed,
                            "score": evaluation.score,
                            "notes": evaluation.notes,
                            "realized_return": evaluation.realized_return,
                            "realized_alpha": evaluation.realized_alpha,
                        },
                    },
                )
            )

    registry.write_entries(registry.load())
    return registry_file, history_file


def print_alpha_mining_success(source: Path, registry_file: Path, history_file: Path) -> None:
    console.print(f"[green]✓ {alpha_text('Alpha mining completed for:', 'Alpha 因子挖掘完成：')}[/green] {source.resolve()}")
    console.print(f"[green]✓ {alpha_text('Registry saved:', 'Registry 已保存：')}[/green] {registry_file.resolve()}")
    console.print(f"[green]✓ {alpha_text('History saved:', 'History 已保存：')}[/green] {history_file.resolve()}")
