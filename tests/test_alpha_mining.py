import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app
from tradingagents.alpha_mining import (
    AlphaCandidate,
    AlphaEvaluator,
    AlphaMiningEpisode,
    AlphaMiningHistory,
    AlphaRegistry,
    AlphaRegistryEntry,
    build_alpha_experience_summary,
    crossover_candidates,
    generate_crossover_set,
    generate_mutation_set,
    mutate_candidate,
)
from tradingagents.agents.managers.factor_manager import create_factor_manager
from tradingagents.dataflows.config import set_config


@pytest.mark.unit
def test_alpha_mutation_and_crossover_behaviors():
    base = AlphaCandidate(
        name="base",
        hypothesis="base hypothesis",
        expression="base_expression",
        signal_score=0.2,
        confidence=0.6,
        complexity=2,
        validation_status="validated_proxy",
        evidence=["e1"],
    )
    mutation = generate_mutation_set(base)
    crossover = crossover_candidates(base, mutation[0], name="blend")
    hybrids = generate_crossover_set([base, mutation[0], mutation[1]])
    assert len(mutation) == 3
    assert crossover.name.startswith("base_")
    assert hybrids
    assert mutation[0].name != base.name


@pytest.mark.unit
def test_alpha_registry_and_history_persist(tmp_path):
    registry_file = tmp_path / "alpha_registry.json"
    history_file = tmp_path / "alpha_history.json"

    registry = AlphaRegistry(registry_file)
    history = AlphaMiningHistory(history_file)
    entry = AlphaRegistryEntry(
        name="base",
        hypothesis="base hypothesis",
        expression="base_expression",
        signal_score=0.2,
        confidence=0.6,
        stability=0.7,
        redundancy_penalty=0.1,
        evidence=["e1"],
        source="sample.json",
        trade_date="2025-02-18",
        realized_return=0.03,
        realized_alpha=0.02,
        evaluation_score=0.71,
    )
    episode = AlphaMiningEpisode(
        source="sample.json",
        ticker="600519.SS",
        trade_date="2025-02-18",
        payload={"alpha": "payload"},
    )

    registry_path = registry.upsert(entry)
    history_path = history.append(episode)

    assert registry_path.exists()
    assert history_path.exists()
    assert registry.load()[0]["name"] == "base"
    assert registry.load()[0]["realized_alpha"] == 0.02
    assert registry.load()[0]["sample_count"] == 1
    assert history.load()[0]["ticker"] == "600519.SS"


@pytest.mark.unit
def test_alpha_registry_upsert_accumulates_samples(tmp_path):
    registry = AlphaRegistry(tmp_path / "alpha_registry.json")
    entry = AlphaRegistryEntry(
        name="base",
        hypothesis="base hypothesis",
        expression="base_expression",
        signal_score=0.2,
        confidence=0.6,
        stability=0.7,
        redundancy_penalty=0.1,
        realized_return=0.03,
        realized_alpha=0.02,
        evaluation_score=0.71,
    )
    registry.upsert(entry)
    registry.upsert(entry)
    rows = registry.load()
    assert rows[0]["sample_count"] == 2
    assert rows[0]["recent_realized_alpha"] == 0.02


@pytest.mark.unit
def test_alpha_evaluator_scores_payload():
    evaluator = AlphaEvaluator()
    result = evaluator.evaluate(
        {
            "selected_alpha": {
                "name": "base",
                "hypothesis": "base hypothesis",
                "expression": "base_expression",
                "signal_score": 0.25,
                "confidence": 0.7,
                "complexity": 2,
                "validation_status": "validated_proxy",
                "evidence": ["e1"],
            },
            "stability": 0.8,
            "redundancy_penalty": 0.1,
            "realized_return": 0.03,
            "realized_alpha": 0.02,
        }
    )
    assert result.passed is True
    assert result.score > 0
    assert result.realized_alpha == 0.02


@pytest.mark.unit
def test_build_alpha_experience_summary_aggregates_registry_and_history():
    summary = build_alpha_experience_summary(
        registry_rows=[
            {
                "name": "alpha_a",
                "realized_return": 0.03,
                "realized_alpha": 0.02,
                "evaluation_score": 0.70,
                "sample_count": 2,
            },
            {
                "name": "alpha_b",
                "realized_return": 0.01,
                "realized_alpha": -0.01,
                "evaluation_score": 0.55,
                "sample_count": 1,
            },
        ],
        history_rows=[
            {"payload": {"alpha_result": {"selected_alpha": {"name": "alpha_a"}}}},
            {"payload": {"alpha_result": {"selected_alpha": {"name": "alpha_b"}}}},
        ],
        selected_alpha={"name": "registry_alpha_a", "validation_status": "registry_reuse"},
    )
    assert summary["registry_entry_count"] == 2
    assert summary["history_episode_count"] == 2
    assert summary["used_registry_experience"] is True
    assert summary["average_realized_alpha"] == pytest.approx(0.005)
    assert summary["selected_alpha_sample_count"] == 2


@pytest.mark.unit
def test_mine_alpha_command_handles_json_state(tmp_path):
    source_dir = tmp_path / "sample"
    source_dir.mkdir()
    state_file = source_dir / "full_states_log_2025-02-18.json"
    state_file.write_text(
        json.dumps(
            {
                "company_of_interest": "600519.SS",
                "trade_date": "2025-02-18",
                "alpha_mining_result": {
                    "selected_alpha": {
                        "name": "seed",
                        "hypothesis": "seed hypothesis",
                        "expression": "seed_expression",
                        "signal_score": 0.3,
                        "confidence": 0.7,
                        "complexity": 2,
                        "validation_status": "validated_proxy",
                        "evidence": ["e1"],
                    },
                    "signal_score": 0.3,
                    "confidence": 0.7,
                    "stability": 0.8,
                    "redundancy_penalty": 0.05,
                    "candidates": [],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["mine-alpha", str(source_dir)])
    assert result.exit_code == 0
    assert (source_dir / "alpha_registry.json").exists()
    assert (source_dir / "alpha_history.json").exists()


@pytest.mark.unit
def test_mine_alpha_registry_only_contains_passed_candidates(tmp_path):
    source_dir = tmp_path / "sample"
    source_dir.mkdir()
    state_file = source_dir / "full_states_log_2025-02-18.json"
    state_file.write_text(
        json.dumps(
            {
                "company_of_interest": "600519.SS",
                "trade_date": "2025-02-18",
                "market_features": {"score": 0.9, "confidence": 0.9},
                "fundamentals_features": {"score": 0.8, "confidence": 0.9},
                "sentiment_features": {"score": 0.2, "confidence": 0.8, "source_coverage": 1.0},
                "news_features": {"score": 0.2, "confidence": 0.8},
                "investment_debate_state": {"signal_score": 0.6},
                "risk_debate_state": {"signal_score": 0.0},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["mine-alpha", str(source_dir)])
    assert result.exit_code == 0

    registry_data = json.loads((source_dir / "alpha_registry.json").read_text(encoding="utf-8"))
    history_data = json.loads((source_dir / "alpha_history.json").read_text(encoding="utf-8"))

    assert registry_data
    assert history_data
    assert len(history_data) >= len(registry_data)


@pytest.mark.unit
def test_factor_manager_appends_live_alpha_history(tmp_path):
    registry_file = tmp_path / "alpha_registry.json"
    history_file = tmp_path / "alpha_history.json"
    set_config(
        {
            "alpha_registry_path": str(registry_file),
            "alpha_history_path": str(history_file),
        }
    )

    node = create_factor_manager()
    result = node(
        {
            "company_of_interest": "600519.SS",
            "trade_date": "2025-02-18",
            "market_features": {"score": 0.8, "confidence": 0.8},
            "fundamentals_features": {"score": 0.4, "confidence": 0.7},
            "sentiment_features": {"score": 0.2, "confidence": 0.6, "source_coverage": 1.0},
            "news_features": {"score": 0.3, "confidence": 0.6},
            "investment_debate_state": {"signal_score": 0.5},
            "risk_debate_state": {"signal_score": 0.0},
        }
    )

    assert "alpha_mining_result" in result
    assert history_file.exists()
    history_rows = json.loads(history_file.read_text(encoding="utf-8"))
    assert history_rows[-1]["source"] == "live_analysis"


@pytest.mark.unit
def test_factor_manager_prefers_ticker_local_alpha_registry(tmp_path):
    results_root = tmp_path / "logs"
    ticker_dir = results_root / "600519.SS" / "TradingAgentsStrategy_logs"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "alpha_registry.json").write_text(
        json.dumps(
            [
                {
                    "name": "local_alpha",
                    "hypothesis": "local hypothesis",
                    "expression": "expr",
                    "signal_score": 0.3,
                    "confidence": 0.8,
                    "stability": 1.0,
                    "redundancy_penalty": 0.0,
                    "evaluation_score": 0.7,
                    "realized_return": 0.03,
                    "realized_alpha": 0.02,
                    "source": "local",
                    "trade_date": "2025-02-18",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (ticker_dir / "alpha_history.json").write_text("[]", encoding="utf-8")

    set_config(
        {
            "results_dir": str(results_root),
            "alpha_registry_path": str(tmp_path / "global_alpha_registry.json"),
            "alpha_history_path": str(tmp_path / "global_alpha_history.json"),
        }
    )

    node = create_factor_manager()
    result = node(
        {
            "company_of_interest": "600519.SS",
            "trade_date": "2025-02-18",
            "market_features": {"score": 0.8, "confidence": 0.8},
            "fundamentals_features": {"score": 0.4, "confidence": 0.7},
            "sentiment_features": {"score": 0.2, "confidence": 0.6, "source_coverage": 1.0},
            "news_features": {"score": 0.3, "confidence": 0.6},
            "investment_debate_state": {"signal_score": 0.5},
            "risk_debate_state": {"signal_score": 0.0},
        }
    )

    assert result["alpha_experience_summary"]["registry_entry_count"] == 1
