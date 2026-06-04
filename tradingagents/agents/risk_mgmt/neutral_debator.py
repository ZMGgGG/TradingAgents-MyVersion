from tradingagents.agents.schemas import (
    RiskDebateSignal,
    RiskStance,
    parse_risk_debate_signal,
    render_risk_debate_signal,
)
from tradingagents.agents.utils.agent_utils import (
    build_compact_feature_context,
    compact_history,
    get_language_instruction,
    get_time_context_instruction,
)
from tradingagents.agents.utils.debate_signals import default_risk_signal, summarize_risk_signals
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_neutral_debator(llm):
    structured_llm = bind_structured(llm, RiskDebateSignal, "Neutral Analyst")

    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        compact_risk_history = compact_history(history, keep_recent_lines=6)
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        first_round = risk_debate_state.get("count", 0) == 0
        market_research_report = state["market_report"] if first_round else "[Use structured feature summary below; full market report omitted after round 1.]"
        sentiment_report = state["sentiment_report"] if first_round else "[Use structured feature summary below; full sentiment report omitted after round 1.]"
        news_report = state["news_report"] if first_round else "[Use structured feature summary below; full news report omitted after round 1.]"
        fundamentals_report = state["fundamentals_report"] if first_round else "[Use structured feature summary below; full fundamentals report omitted after round 1.]"
        feature_context = build_compact_feature_context(state)

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

{feature_context}

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {compact_risk_history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the conservative analyst: {current_conservative_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes.
First write your normal debate response in natural language. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
STANCE: Neutral
SCORE: <0.00 to 1.00>
CONFIDENCE: <0.00 to 1.00>
EVIDENCE_QUALITY: <0.00 to 1.00>
TIME_HORIZON_DAYS: <integer>
THESIS: <one concise thesis>
GUARDRAILS: <balanced operating guardrails>
END_STRUCTURED_SUMMARY

Keep the debate body rich and persuasive. The summary block should be brief and only appear once at the end.
{get_time_context_instruction(state)}""" + get_language_instruction()

        rendered_signal, signal = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_risk_debate_signal,
            "Neutral Analyst",
            fallback=lambda text: parse_risk_debate_signal(
                text,
                "Neutral Analyst",
                RiskStance.NEUTRAL,
            ),
        )
        signal = signal or default_risk_signal(
            RiskStance.NEUTRAL,
            rendered_signal,
            "Neutral Analyst",
        )

        argument = f"Neutral Analyst:\n{rendered_signal}"
        summary = summarize_risk_signals(
            RiskDebateSignal.model_validate(risk_debate_state["aggressive_signal"])
            if risk_debate_state.get("aggressive_signal")
            else None,
            RiskDebateSignal.model_validate(risk_debate_state["conservative_signal"])
            if risk_debate_state.get("conservative_signal")
            else None,
            signal,
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
            "judge_decision": risk_debate_state.get("judge_decision", ""),
            "aggressive_signal": risk_debate_state.get("aggressive_signal", {}),
            "conservative_signal": risk_debate_state.get("conservative_signal", {}),
            "neutral_signal": signal.model_dump(),
            "signal_summary": summary["summary"],
            "signal_score": summary["net_score"],
            "signal_confidence": summary["average_confidence"],
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
