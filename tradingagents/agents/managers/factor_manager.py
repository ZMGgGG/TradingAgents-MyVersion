from __future__ import annotations

from tradingagents.decisioning.factor_engine import FactorEngine


def create_factor_manager() -> callable:
    factor_engine = FactorEngine()

    def factor_manager_node(state) -> dict:
        factor_score = factor_engine.score(state)
        return {
            "factor_score": factor_score.model_dump(),
        }

    return factor_manager_node
