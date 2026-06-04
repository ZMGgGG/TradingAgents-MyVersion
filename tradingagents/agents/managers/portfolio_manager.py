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
    PortfolioDecision,
    parse_pm_decision,
    render_pm_decision,
)
from tradingagents.agents.utils.agent_utils import (
    build_compact_feature_context,
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        feature_context = build_compact_feature_context(state)

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

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
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

First write your natural-language final decision memo. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
RATING: <Buy|Overweight|Hold|Underweight|Sell>
EXECUTIVE_SUMMARY: <two to three concise sentences>
INVESTMENT_THESIS: <concise thesis>
PRICE_TARGET: <optional number>
TIME_HORIZON: <optional text>
TARGET_POSITION_SIZE: <optional decimal like 0.05>
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
        final_trade_decision = (
            render_pm_decision(structured_decision)
            if structured_decision is not None
            else rendered_decision
        )

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
        }

    return portfolio_manager_node
