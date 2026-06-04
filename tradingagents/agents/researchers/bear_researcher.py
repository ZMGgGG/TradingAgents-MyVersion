from tradingagents.agents.schemas import (
    InvestmentDebateSignal,
    InvestmentStance,
    parse_investment_debate_signal,
    render_investment_debate_signal,
)
from tradingagents.agents.utils.agent_utils import (
    build_compact_feature_context,
    compact_history,
    get_language_instruction,
    get_time_context_instruction,
)
from tradingagents.agents.utils.debate_signals import (
    default_investment_signal,
    summarize_investment_signals,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_bear_researcher(llm):
    structured_llm = bind_structured(llm, InvestmentDebateSignal, "Bear Researcher")

    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        compact_debate_history = compact_history(history, keep_recent_lines=6)
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        feature_context = build_compact_feature_context(state)
        first_round = investment_debate_state.get("count", 0) == 0
        market_research_report = state["market_report"] if first_round else "[Use structured feature summary below; full market report omitted after round 1.]"
        sentiment_report = state["sentiment_report"] if first_round else "[Use structured feature summary below; full sentiment report omitted after round 1.]"
        news_report = state["news_report"] if first_round else "[Use structured feature summary below; full news report omitted after round 1.]"
        fundamentals_report = state["fundamentals_report"] if first_round else "[Use structured feature summary below; full fundamentals report omitted after round 1.]"
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bear Analyst making the case against investing in the {target_label}. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

Structured analyst feature summary:
{feature_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {compact_debate_history}
Last bull argument: {current_response}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the {target_label}.
First write your normal debate response in natural language. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
STANCE: Bearish
SCORE: <0.00 to 1.00>
CONFIDENCE: <0.00 to 1.00>
EVIDENCE_QUALITY: <0.00 to 1.00>
TIME_HORIZON_DAYS: <integer>
THESIS: <one concise thesis>
REBUTTAL: <main rebuttal to the bull case>
KEY_RISKS: <main risks to the bear case>
END_STRUCTURED_SUMMARY

Keep the debate body rich and persuasive. The summary block should be brief and only appear once at the end.
{get_time_context_instruction(state)}""" + get_language_instruction()

        rendered_signal, signal = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_investment_debate_signal,
            "Bear Researcher",
            fallback=lambda text: parse_investment_debate_signal(
                text,
                "Bear Researcher",
                InvestmentStance.BEARISH,
            ),
        )
        signal = signal or default_investment_signal(
            InvestmentStance.BEARISH,
            rendered_signal,
            "Bear Researcher",
        )

        argument = f"Bear Analyst:\n{rendered_signal}"
        summary = summarize_investment_signals(
            InvestmentDebateSignal.model_validate(investment_debate_state["bull_signal"])
            if investment_debate_state.get("bull_signal")
            else None,
            signal,
        )

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
            "judge_decision": investment_debate_state.get("judge_decision", ""),
            "bull_signal": investment_debate_state.get("bull_signal", {}),
            "bear_signal": signal.model_dump(),
            "signal_summary": summary["summary"],
            "signal_score": summary["net_score"],
            "signal_confidence": summary["average_confidence"],
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
