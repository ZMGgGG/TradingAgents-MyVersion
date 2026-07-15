from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.schemas import parse_analyst_feature_summary
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_compact_report_instruction,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_language_instruction,
    get_time_context_from_state,
)
from tradingagents.dataflows.config import get_config


def _build_fundamentals_evidence_ledger(
    *,
    ticker: str,
    as_of_date: str,
    lookback_days: int,
) -> dict:
    return {
        "ticker": ticker,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "sources": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
        ],
    }


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        time_context = get_time_context_from_state(state)
        current_date = time_context.as_of_date
        lookback_days = time_context.analysis_lookback_days
        instrument_context = (
            build_instrument_context(state["company_of_interest"])
            + " "
            + time_context.to_prompt_string()
        )

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            f"You are a researcher tasked with analyzing fundamental information over the past {lookback_days} days about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_compact_report_instruction()
            + " After the full report, append exactly one machine-readable block in this format: FEATURE_SUMMARY / SCORE / CONFIDENCE / KEY_SIGNAL / RISK_FLAG / END_FEATURE_SUMMARY."
            + " Prefer `get_fundamentals` as the primary comprehensive source. Use `get_balance_sheet`, `get_cashflow`, and `get_income_statement` only as optional supplements; if a specific statement is unavailable, continue with the available evidence and state the limitation."
            + get_language_instruction(),
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
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""
        features = {}
        evidence_ledger = _build_fundamentals_evidence_ledger(
            ticker=state["company_of_interest"],
            as_of_date=current_date,
            lookback_days=lookback_days,
        )

        if len(result.tool_calls) == 0:
            report = result.content
            features = parse_analyst_feature_summary(report).model_dump()

        return {
            "messages": [result],
            "fundamentals_report": report,
            "fundamentals_features": features,
            "fundamentals_evidence_ledger": evidence_ledger,
        }

    return fundamentals_analyst_node
