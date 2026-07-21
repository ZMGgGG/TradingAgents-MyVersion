"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import (
    ExecutionPlan,
    PortfolioDecision,
    parse_pm_decision,
    render_pm_decision,
)
from tradingagents.decisioning.execution_policy import (
    normalize_target_position_size,
    rating_to_execution_action,
)
from tradingagents.agents.utils.agent_utils import (
    build_compact_feature_context,
    build_data_quality_context,
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    has_structured_summary_block,
    invoke_structured_or_freetext_result,
)


def _sanitize_price_target(decision: PortfolioDecision | None, state: dict) -> None:
    """Drop obviously misparsed price targets, especially horizon numbers."""
    if decision is None or decision.price_target is None:
        return
    market_ledger = state.get("market_evidence_ledger", {}) or {}
    crypto_snapshot = market_ledger.get("crypto_snapshot", {}) or {}
    latest_close = crypto_snapshot.get("latest_close")
    try:
        latest_close_float = float(latest_close)
    except (TypeError, ValueError):
        return
    if latest_close_float <= 0:
        return
    target = float(decision.price_target)
    if target <= 0 or target < latest_close_float * 0.2 or target > latest_close_float * 5:
        decision.price_target = None


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        asset_type = state.get("asset_type", "stock")
        instrument_context = build_instrument_context(state["company_of_interest"], asset_type)
        feature_context = build_compact_feature_context(state)
        data_quality_context = build_data_quality_context(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]
        risk_signal_summary = state["risk_debate_state"].get("signal_summary", "")
        factor_score = state.get("factor_score", {})
        position_sizing = state.get("position_sizing", {})
        risk_gate_result = state.get("risk_gate_result", {})

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}
{feature_context}
{data_quality_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: No new action; keep target position size blank or 0 because current holdings are not known to this system
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
- Deterministic factor score: **{factor_score}**
- Deterministic position sizing plan: **{position_sizing}**
- Deterministic risk gate result: **{risk_gate_result}**
{lessons_line}
**Risk Analysts Debate History:**
{history}

**Structured Risk Summary:**
{risk_signal_summary}

---

Be decisive and ground every conclusion in specific evidence from the analysts.
For crypto assets, missing derivatives/on-chain/social data is a data-quality limitation, not directional evidence. Do not infer crowding, liquidation pressure, or accumulation from source silence.

First write your natural-language final decision memo. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
RATING: <Buy|Overweight|Hold|Underweight|Sell>
EXECUTIVE_SUMMARY: <two to three concise sentences>
INVESTMENT_THESIS: <concise thesis>
PRICE_TARGET: <optional price number only; leave blank if no price target is justified>
TIME_HORIZON: <optional text>
TARGET_POSITION_SIZE: <optional decimal like 0.05; use 0 or leave blank for Hold>
RISK_GATE_STATUS: <optional short status>
END_STRUCTURED_SUMMARY

Keep the main decision memo readable for humans. The summary block should be brief and only appear once at the end.{get_language_instruction()}"""

        rendered_decision, structured_decision = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
            fallback=parse_pm_decision,
        )
        rendered_structured_decision = (
            render_pm_decision(structured_decision)
            if structured_decision is not None
            else ""
        )
        should_render_structured_decision = (
            structured_decision is not None
            and (
                rendered_decision == rendered_structured_decision
                or has_structured_summary_block(rendered_decision)
            )
        )
        final_trade_decision = rendered_structured_decision if should_render_structured_decision else rendered_decision
        _sanitize_price_target(structured_decision, state)
        if structured_decision is not None and structured_decision.rating.value.lower() == "hold":
            structured_decision.target_position_size = 0.0
        if should_render_structured_decision:
            final_trade_decision = render_pm_decision(structured_decision)

        if risk_gate_result and not risk_gate_result.get("approved", True):
            forced_rating = risk_gate_result.get("forced_rating", "Hold")
            reasons = "; ".join(risk_gate_result.get("reasons", [])) or "Deterministic risk gate blocked the trade."
            final_trade_decision = "\n".join([
                f"**Rating**: {forced_rating}",
                "",
                f"**Executive Summary**: Trade blocked by deterministic risk gate.",
                "",
                f"**Investment Thesis**: {reasons}",
                "",
                f"**Risk Gate Status**: Blocked",
            ])

        risk_gate_approved = bool(risk_gate_result.get("approved", True))
        if not risk_gate_approved:
            target_position_size = 0.0
            action = "hold"
        else:
            rating_text = (
                structured_decision.rating.value.lower()
                if structured_decision is not None
                else "hold"
            )
            action = rating_to_execution_action(rating_text)
            target_position_size = float(
                risk_gate_result.get(
                    "capped_position_size",
                    position_sizing.get("target_position_size", 0.0),
                )
            )
            target_position_size = normalize_target_position_size(action, target_position_size)

        execution_plan = ExecutionPlan(
            action=action,
            target_position_size=max(0.0, min(1.0, target_position_size)),
            holding_days=5,
            risk_gate_approved=risk_gate_approved,
            stop_loss_buffer=position_sizing.get("stop_loss_buffer"),
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
            "aggressive_signal": risk_debate_state.get("aggressive_signal", {}),
            "conservative_signal": risk_debate_state.get("conservative_signal", {}),
            "neutral_signal": risk_debate_state.get("neutral_signal", {}),
            "signal_summary": risk_debate_state.get("signal_summary", ""),
            "signal_score": risk_debate_state.get("signal_score", 0.0),
            "signal_confidence": risk_debate_state.get("signal_confidence", 0.0),
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "execution_plan": execution_plan.model_dump(),
        }

    return portfolio_manager_node
