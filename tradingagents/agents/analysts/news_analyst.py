from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.schemas import parse_analyst_feature_summary
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_compact_report_instruction,
    get_global_news,
    get_insider_transactions,
    get_language_instruction,
    get_news,
    get_time_context_from_state,
)
from tradingagents.content_discovery import discover_related_content
from tradingagents.content_discovery.planner import render_discovery_context


def _build_news_evidence_ledger(discovery) -> dict:
    return {
        "ticker": discovery.ticker,
        "window": {
            "start_date": discovery.start_date,
            "end_date": discovery.end_date,
        },
        "expanded_queries": discovery.expanded_queries,
        "source_count": discovery.source_count,
        "source_diversity": discovery.source_diversity,
        "has_primary_content": bool(discovery.company_blocks),
        "has_related_content": bool(discovery.related_blocks),
        "has_macro_content": bool(discovery.macro_block.strip()),
        "summary": discovery.summary,
    }


def _should_enable_news_tools(discovery) -> bool:
    if int(getattr(discovery, "source_count", 0) or 0) == 0:
        return True
    has_primary = bool(getattr(discovery, "company_blocks", None))
    has_related = bool(getattr(discovery, "related_blocks", None))
    has_macro = bool(str(getattr(discovery, "macro_block", "") or "").strip())
    return not (has_primary or has_related or has_macro)


def create_news_analyst(llm):
    def news_analyst_node(state):
        time_context = get_time_context_from_state(state)
        current_date = time_context.as_of_date
        lookback_days = time_context.analysis_lookback_days
        asset_type = state.get("asset_type", "stock")
        asset_label = "company" if asset_type == "stock" else "asset"
        instrument_context = build_instrument_context(
            state["company_of_interest"], asset_type
        ) + " " + time_context.to_prompt_string()
        discovery = discover_related_content(
            ticker=state["company_of_interest"],
            start_date=time_context.news_start_date(),
            end_date=current_date,
            lookback_days=lookback_days,
            asset_type=asset_type,
        )

        tools = [get_news, get_global_news]
        if asset_type == "stock":
            tools.append(get_insider_transactions)
        use_tools = _should_enable_news_tools(discovery)

        system_message = (
            f"You are a news researcher tasked with analyzing recent news and trends over the past {lookback_days} days. A deterministic content discovery layer has already expanded the related queries and fetched primary, related, and macro content for this {asset_label}. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_compact_report_instruction()
            + " After the full report, append exactly one machine-readable block in this format: FEATURE_SUMMARY / SCORE / CONFIDENCE / KEY_SIGNAL / RISK_FLAG / END_FEATURE_SUMMARY."
            + get_language_instruction()
        )
        if use_tools:
            system_message += (
                " Content discovery returned sparse results. You may use the provided news tools "
                "to fill specific missing event or macro context. If tool results are already present "
                "in the message history, synthesize the final report instead of calling more tools."
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("user", "{discovery_context}"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(discovery_context=render_discovery_context(discovery))

        chain = prompt | (llm.bind_tools(tools) if use_tools else llm)
        result = chain.invoke(state["messages"])

        report = "" if getattr(result, "tool_calls", None) else result.content
        features = parse_analyst_feature_summary(report).model_dump() if report else {}
        evidence_ledger = _build_news_evidence_ledger(discovery)
        evidence_ledger["tool_fallback_enabled"] = use_tools

        return {
            "messages": [result],
            "news_report": report,
            "news_features": features,
            "news_evidence_ledger": evidence_ledger,
        }

    return news_analyst_node
