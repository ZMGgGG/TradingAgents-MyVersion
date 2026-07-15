from tradingagents.agents.schemas import (
    InvestmentDebateSignal,
    InvestmentStance,
    parse_investment_debate_signal,
    render_investment_debate_signal,
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
from tradingagents.agents.utils.debate_signals import (
    default_investment_signal,
    summarize_investment_signals,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_result,
)


def create_bull_researcher(llm):
    structured_llm = bind_structured(llm, InvestmentDebateSignal, "Bull Researcher")

    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        compact_debate_history = compact_history(history, keep_recent_lines=6)
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        feature_context = build_compact_feature_context(state)
        data_quality_context = build_data_quality_context(state)
        quant_context = build_quant_summary_context(state)
        first_round = investment_debate_state.get("count", 0) == 0
        market_research_report = build_report_evidence_pack(state, report_key="market_report", features_key="market_features", label="Market") if first_round else "[Use structured feature summary below; full market report omitted after round 1.]"
        sentiment_report = build_report_evidence_pack(state, report_key="sentiment_report", features_key="sentiment_features", label="Sentiment") if first_round else "[Use structured feature summary below; full sentiment report omitted after round 1.]"
        news_report = build_report_evidence_pack(state, report_key="news_report", features_key="news_features", label="News") if first_round else "[Use structured feature summary below; full news report omitted after round 1.]"
        fundamentals_report = build_report_evidence_pack(state, report_key="fundamentals_report", features_key="fundamentals_features", label="Fundamentals") if first_round else "[Use structured feature summary below; full fundamentals report omitted after round 1.]"
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bull Analyst advocating for investing in the {target_label}. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
Structured analyst feature summary:
{feature_context}
{data_quality_context}
{quant_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {compact_debate_history}
Last bear argument: {current_response}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.
Avoid repeating the same thesis in multiple phrasings. Add at least one quantified or scenario-based argument when possible (for example: what happens if the current factor composite persists, or if sentiment/data quality improves).
Keep the debate body concise: no more than 4 short paragraphs or bullets, under 900 Chinese characters or 450 English words. Do not restate full analyst reports; cite only the strongest evidence.
First write your normal debate response in natural language. Then append a machine-readable summary block in exactly this format:

STRUCTURED_SUMMARY
STANCE: Bullish
SCORE: <0.00 to 1.00>
CONFIDENCE: <0.00 to 1.00>
EVIDENCE_QUALITY: <0.00 to 1.00>
TIME_HORIZON_DAYS: <integer>
THESIS: <one concise thesis>
REBUTTAL: <main rebuttal to the bear case>
KEY_RISKS: <main risks to the bull case>
END_STRUCTURED_SUMMARY

Keep the summary block brief and only appear once at the end.
{get_time_context_instruction(state)}""" + get_language_instruction()

        rendered_signal, signal = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            prompt,
            render_investment_debate_signal,
            "Bull Researcher",
            fallback=lambda text: parse_investment_debate_signal(
                text,
                "Bull Researcher",
                InvestmentStance.BULLISH,
            ),
        )
        signal = signal or default_investment_signal(
            InvestmentStance.BULLISH,
            rendered_signal,
            "Bull Researcher",
        )

        argument = f"Bull Analyst:\n{rendered_signal}"
        summary = summarize_investment_signals(
            signal,
            InvestmentDebateSignal.model_validate(investment_debate_state["bear_signal"])
            if investment_debate_state.get("bear_signal")
            else None,
        )

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
            "judge_decision": investment_debate_state.get("judge_decision", ""),
            "bull_signal": signal.model_dump(),
            "bear_signal": investment_debate_state.get("bear_signal", {}),
            "signal_summary": summary["summary"],
            "signal_score": summary["net_score"],
            "signal_confidence": summary["average_confidence"],
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
