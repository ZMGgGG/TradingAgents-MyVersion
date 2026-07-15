from pathlib import Path

import pytest

from cli.main import discover_alpha_sources


@pytest.mark.unit
def test_discover_alpha_sources_finds_saved_state_logs(tmp_path: Path):
    logs_dir = tmp_path / ".tradingagents" / "logs" / "300308.SZ" / "TradingAgentsStrategy_logs"
    logs_dir.mkdir(parents=True)
    target = logs_dir / "full_states_log_2026-06-26.json"
    target.write_text("{}", encoding="utf-8")

    matches = discover_alpha_sources(tmp_path / ".tradingagents" / "logs")
    assert target in matches
