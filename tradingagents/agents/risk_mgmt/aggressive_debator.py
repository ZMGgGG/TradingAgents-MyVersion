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


def create_aggressive_debator(llm):
    structured_llm = bind_structured(llm, RiskDebateSignal, "Aggressive Analyst")

    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        compact_risk_history = compact_history(history, keep_recent_lines=6)
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        first_round = risk_debate_state.get("count", 0) == 0
        market_research_report = state["market_report"] if first_round else "[Use structured feature summary below; full market report omitted after round 1.]"
        sentiment_report = state["sentiment_report"] if first_round else "[Use structured feature summary below; full sentiment report omitted after round 1.]"
        news_report = state["news_report"] if first_round else "[Use structured feature summary below; full news report omitted after round 1.]"
        fundamentals_report = state["fundamentals_report"] if first_round else "[Use structured feature summary below; full fundamentals report omitted after round 1.]"
        feature_context = build_compact_feature_context(state)

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative. Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

{feature_context}

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {compact_risk_history} Here are the last arguments from the conservative analyst: {current_conservative_response} Here are the last arguments from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, not just presenting data. Challenge each counterpoint to underscore why a high-risk approach is optimal.
First write your normal debate response in natural language. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
STANCE: Aggressive
SCORE: <0.00 to 1.00>
CONFIDENCE: <0.00 to 1.00>
EVIDENCE_QUALITY: <0.00 to 1.00>
TIME_HORIZON_DAYS: <integer>
THESIS: <one concise thesis>
GUARDRAILS: <risk guardrails or risk-taking conditions>
END_STRUCTURED_SUMMARY

Keep the debate body rich and persuasive. The summary block should be brief and only appear once at the end.
{get_time_context_instruction(state)}""" + get_language_instruction()

        rendered_signal, signal = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_risk_debate_signal,
            "Aggressive Analyst",
            fallback=lambda text: parse_risk_debate_signal(
                text,
                "Aggressive Analyst",
                RiskStance.AGGRESSIVE,
            ),
        )
        signal = signal or default_risk_signal(
            RiskStance.AGGRESSIVE,
            rendered_signal,
            "Aggressive Analyst",
        )

        argument = f"Aggressive Analyst:\n{rendered_signal}"
        summary = summarize_risk_signals(
            signal,
            RiskDebateSignal.model_validate(risk_debate_state["conservative_signal"])
            if risk_debate_state.get("conservative_signal")
            else None,
            RiskDebateSignal.model_validate(risk_debate_state["neutral_signal"])
            if risk_debate_state.get("neutral_signal")
            else None,
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
            "judge_decision": risk_debate_state.get("judge_decision", ""),
            "aggressive_signal": signal.model_dump(),
            "conservative_signal": risk_debate_state.get("conservative_signal", {}),
            "neutral_signal": risk_debate_state.get("neutral_signal", {}),
            "signal_summary": summary["summary"],
            "signal_score": summary["net_score"],
            "signal_confidence": summary["average_confidence"],
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
