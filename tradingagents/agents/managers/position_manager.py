from __future__ import annotations

from tradingagents.decisioning.position_sizing import PositionSizer


def create_position_manager() -> callable:
    position_sizer = PositionSizer()

    def position_manager_node(state) -> dict:
        position_plan = position_sizer.size(state)
        return {
            "position_sizing": position_plan.model_dump(),
        }

    return position_manager_node
