from __future__ import annotations

from pathlib import Path

from tradingagents.alpha_mining import (
    AlphaMiningEpisode,
    AlphaMiningHistory,
    AlphaRegistry,
    QuantaAlphaMiner,
    build_alpha_experience_summary,
)
from tradingagents.decisioning.factor_engine import FactorEngine
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.utils import safe_ticker_component


def create_factor_manager() -> callable:
    factor_engine = FactorEngine()

    def factor_manager_node(state) -> dict:
        config = get_config()
        ticker = str(state.get("company_of_interest", ""))
        safe_ticker = safe_ticker_component(ticker) if ticker else ""
        ticker_log_dir = (
            Path(config["results_dir"]) / safe_ticker / "TradingAgentsStrategy_logs"
            if safe_ticker
            else None
        )
        registry_path = (
            ticker_log_dir / "alpha_registry.json"
            if ticker_log_dir is not None and (ticker_log_dir / "alpha_registry.json").exists()
            else Path(config["alpha_registry_path"])
        )
        history_path = (
            ticker_log_dir / "alpha_history.json"
            if ticker_log_dir is not None and (ticker_log_dir / "alpha_history.json").exists()
            else Path(config["alpha_history_path"])
        )
        registry = AlphaRegistry(registry_path)
        history = AlphaMiningHistory(history_path)
        alpha_miner = QuantaAlphaMiner(registry=registry, history=history)
        alpha_result = alpha_miner.mine(state)
        episode = AlphaMiningEpisode(
            source="live_analysis",
            ticker=str(state.get("company_of_interest", "")),
            trade_date=str(state.get("trade_date", "")),
            payload={
                "alpha_result": alpha_result.model_dump(),
            },
        )
        setattr(episode, "asset_type", str(state.get("asset_type", "stock")))
        history.append(episode)
        alpha_experience_summary = build_alpha_experience_summary(
            registry.load(),
            history.load(),
            selected_alpha=alpha_result.model_dump().get("selected_alpha", {}),
        )
        scoring_state = {
            **state,
            "alpha_mining_result": alpha_result.model_dump(),
        }
        factor_score = factor_engine.score(scoring_state)
        return {
            "alpha_mining_result": alpha_result.model_dump(),
            "alpha_experience_summary": alpha_experience_summary,
            "factor_score": factor_score.model_dump(),
        }

    return factor_manager_node
