from pathlib import Path

import pytest

from frontend import server
from tradingagents.default_config import DEFAULT_CONFIG


@pytest.mark.unit
def test_build_run_config_deep_copies_defaults():
    config = server._build_run_config({"user_id": "alice"})

    assert config is not DEFAULT_CONFIG
    assert config["data_vendors"] is not DEFAULT_CONFIG["data_vendors"]
    assert config["tool_vendors"] is not DEFAULT_CONFIG["tool_vendors"]


@pytest.mark.unit
def test_semantic_simulation_api_paths_alias_legacy_handlers():
    assert server._canonical_api_path("/api/simulation/forecast/order") == "/api/paper/order"
    assert server._canonical_api_path("/api/simulation/backtest/manual") == "/api/paper/replay-manual"
    assert server._canonical_api_path("/api/simulation/observation/intraday") == "/api/paper/intraday"
    assert server._canonical_api_path("/api/simulation/episodes") == "/api/paper/episodes"
    assert server._canonical_api_path("/api/observations/from-run") == "/api/conclusions/from-run"
    assert server._canonical_api_path("/api/paper/order") == "/api/paper/order"


@pytest.mark.unit
def test_build_run_config_keeps_task_api_key_out_of_environment(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_CN_API_KEY", raising=False)

    config = server._build_run_config(
        {
            "user_id": "alice",
            "ensure_api_key": True,
            "api_key_env_name": "DASHSCOPE_CN_API_KEY",
            "api_key_value": "sk-task-local",
        }
    )

    assert config["api_key"] == "sk-task-local"
    assert "DASHSCOPE_CN_API_KEY" not in server.os.environ


@pytest.mark.unit
def test_resolve_reference_path_allows_project_research_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    reference = tmp_path / "研报" / "reference.md"
    reference.parent.mkdir()
    reference.write_text("reference", encoding="utf-8")

    resolved = server._resolve_reference_path("研报/reference.md", "alice")

    assert resolved == reference.resolve()


@pytest.mark.unit
def test_resolve_reference_path_rejects_outside_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError):
        server._resolve_reference_path(str(outside), "alice")


@pytest.mark.unit
def test_update_stream_phase_publishes_factor_manager_output():
    run = {
        "agent_status": {"Factor Manager": "pending"},
        "agent_outputs": {},
        "attachments": {},
        "events": [],
        "logs": [],
    }

    server._update_stream_phase(
        run,
        {"investment_debate_state": {"judge_decision": "research done"}},
        ["market"],
    )

    assert run["agent_status"]["Factor Manager"] == "in_progress"

    server._update_stream_phase(
        run,
        {
            "investment_debate_state": {"judge_decision": "research done"},
            "factor_score": {"composite_score": 0.12, "summary": "factor summary"},
            "alpha_mining_result": {
                "signal_score": 0.34,
                "confidence": 0.56,
                "selected_alpha": {"name": "trend_quality"},
            },
        },
        ["market"],
    )

    assert run["agent_status"]["Factor Manager"] == "completed"
    assert run["attachments"]["factor_runtime_source"] == "stream"
    assert run["attachments"]["factor_runtime_detail"]["composite_score"] == 0.12
    assert "trend_quality" in run["agent_outputs"]["Factor Manager"]

    server._update_stream_phase(
        run,
        {"investment_debate_state": {"judge_decision": "research done"}},
        ["market"],
    )

    assert run["agent_status"]["Factor Manager"] == "completed"


@pytest.mark.unit
def test_factor_backfill_overwrites_stale_pending_status():
    run = {
        "status": "completed",
        "agent_status": {"Factor Manager": "pending"},
        "agent_outputs": {},
        "attachments": {},
        "final_state": {
            "factor_score": {"composite_score": 0.21, "summary": "factor summary"},
            "alpha_mining_result": {
                "signal_score": 0.43,
                "confidence": 0.65,
                "selected_alpha": {"name": "momentum_quality"},
            },
        },
    }

    server._backfill_factor_runtime_from_state_log(run)

    assert run["agent_status"]["Factor Manager"] == "completed"
    assert run["attachments"]["factor_runtime_detail"]["composite_score"] == 0.21
    assert "momentum_quality" in run["agent_outputs"]["Factor Manager"]
