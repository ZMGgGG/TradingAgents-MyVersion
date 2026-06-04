from __future__ import annotations

from tradingagents.decisioning.risk_gate import RiskGate


def create_risk_gate_manager() -> callable:
    risk_gate = RiskGate()

    def risk_gate_node(state) -> dict:
        result = risk_gate.evaluate(state)
        return {
            "risk_gate_result": result.model_dump(),
        }

    return risk_gate_node
