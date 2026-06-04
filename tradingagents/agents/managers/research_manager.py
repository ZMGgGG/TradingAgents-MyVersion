"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.schemas import (
    ResearchPlan,
    parse_research_plan,
    render_research_plan,
)
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_compact_feature_context,
    compact_history,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_research_manager(llm):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        feature_context = build_compact_feature_context(state)
        history = state["investment_debate_state"].get("history", "")
        compact_debate_history = compact_history(history, keep_recent_lines=8)
        signal_summary = state["investment_debate_state"].get("signal_summary", "")

        investment_debate_state = state["investment_debate_state"]

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

{instrument_context}
{feature_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position

Commit to a clear stance whenever the debate's strongest arguments warrant one; reserve Hold for situations where the evidence on both sides is genuinely balanced.

---

**Debate History:**
{compact_debate_history}

**Structured Debate Summary:**
{signal_summary}

First write your natural-language decision memo. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
RECOMMENDATION: <Buy|Overweight|Hold|Underweight|Sell>
RATIONALE: <one concise rationale>
STRATEGIC_ACTIONS: <one concise action plan>
END_STRUCTURED_SUMMARY

Keep the main decision memo readable for humans. The summary block should be brief and only appear once at the end.""" + get_language_instruction()

        rendered_plan, structured_plan = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
            fallback=parse_research_plan,
        )
        investment_plan = (
            render_research_plan(structured_plan)
            if structured_plan is not None
            else rendered_plan
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
            "bull_signal": investment_debate_state.get("bull_signal", {}),
            "bear_signal": investment_debate_state.get("bear_signal", {}),
            "signal_summary": investment_debate_state.get("signal_summary", ""),
            "signal_score": investment_debate_state.get("signal_score", 0.0),
            "signal_confidence": investment_debate_state.get("signal_confidence", 0.0),
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
