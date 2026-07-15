from tradingagents.agents.schemas import (
    RiskDebateSignal,
    RiskStance,
    parse_risk_debate_signal,
    render_risk_debate_signal,
)
from tradingagents.agents.utils.agent_utils import (
    build_compact_feature_context,
    build_data_quality_context,
    build_quant_summary_context,
    build_report_evidence_pack,
    compact_history,
    get_language_instruction,
    get_time_context_instruction,
)
from tradingagents.agents.utils.debate_signals import default_risk_signal, summarize_risk_signals
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_conservative_debator(llm):
    structured_llm = bind_structured(llm, RiskDebateSignal, "Conservative Analyst")

    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        compact_risk_history = compact_history(history, keep_recent_lines=6)
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        first_round = risk_debate_state.get("count", 0) == 0
        market_research_report = build_report_evidence_pack(state, report_key="market_report", features_key="market_features", label="Market") if first_round else "[Use structured feature summary below; full market report omitted after round 1.]"
        sentiment_report = build_report_evidence_pack(state, report_key="sentiment_report", features_key="sentiment_features", label="Sentiment") if first_round else "[Use structured feature summary below; full sentiment report omitted after round 1.]"
        news_report = build_report_evidence_pack(state, report_key="news_report", features_key="news_features", label="News") if first_round else "[Use structured feature summary below; full news report omitted after round 1.]"
        fundamentals_report = build_report_evidence_pack(state, report_key="fundamentals_report", features_key="fundamentals_features", label="Fundamentals") if first_round else "[Use structured feature summary below; full fundamentals report omitted after round 1.]"
        feature_context = build_compact_feature_context(state)
        data_quality_context = build_data_quality_context(state)
        quant_context = build_quant_summary_context(state)

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

{feature_context}
{data_quality_context}
{quant_context}

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {compact_risk_history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches.
Avoid repeating points already covered unless you are adding a new number, a new downside scenario, or a clearer quantified trade-off.
Keep the debate body concise: no more than 4 short paragraphs or bullets, under 900 Chinese characters or 450 English words. Do not restate full analyst reports; cite only the strongest evidence.
First write your normal debate response in natural language. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
STANCE: Conservative
SCORE: <0.00 to 1.00>
CONFIDENCE: <0.00 to 1.00>
EVIDENCE_QUALITY: <0.00 to 1.00>
TIME_HORIZON_DAYS: <integer>
THESIS: <one concise thesis>
GUARDRAILS: <main risk controls or defensive posture>
END_STRUCTURED_SUMMARY

Keep the summary block brief and only appear once at the end.
{get_time_context_instruction(state)}""" + get_language_instruction()

        rendered_signal, signal = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_risk_debate_signal,
            "Conservative Analyst",
            fallback=lambda text: parse_risk_debate_signal(
                text,
                "Conservative Analyst",
                RiskStance.CONSERVATIVE,
            ),
        )
        signal = signal or default_risk_signal(
            RiskStance.CONSERVATIVE,
            rendered_signal,
            "Conservative Analyst",
        )

        argument = f"Conservative Analyst:\n{rendered_signal}"
        summary = summarize_risk_signals(
            RiskDebateSignal.model_validate(risk_debate_state["aggressive_signal"])
            if risk_debate_state.get("aggressive_signal")
            else None,
            signal,
            RiskDebateSignal.model_validate(risk_debate_state["neutral_signal"])
            if risk_debate_state.get("neutral_signal")
            else None,
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
            "judge_decision": risk_debate_state.get("judge_decision", ""),
            "aggressive_signal": risk_debate_state.get("aggressive_signal", {}),
            "conservative_signal": signal.model_dump(),
            "neutral_signal": risk_debate_state.get("neutral_signal", {}),
            "signal_summary": summary["summary"],
            "signal_score": summary["net_score"],
            "signal_confidence": summary["average_confidence"],
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
