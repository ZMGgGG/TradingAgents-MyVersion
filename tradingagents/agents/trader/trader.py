"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

import functools

from langchain_core.messages import AIMessage

from tradingagents.agents.schemas import (
    TraderProposal,
    parse_trader_proposal,
    render_trader_proposal,
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


def create_trader(llm):
    structured_llm = bind_structured(llm, TraderProposal, "Trader")

    def trader_node(state, name):
        company_name = state["company_of_interest"]
        asset_type = state.get("asset_type", "stock")
        instrument_context = build_instrument_context(company_name, asset_type)
        feature_context = build_compact_feature_context(state)
        investment_plan = state["investment_plan"]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a trading agent analyzing market data to make investment decisions. "
                    "Based on your analysis, provide a specific recommendation to buy, sell, or hold. "
                    "Anchor your reasoning in the analysts' reports and the research plan."
                    + get_language_instruction()
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Based on a comprehensive analysis by a team of analysts, here is an investment "
                    f"plan tailored for {company_name}. {instrument_context} This plan incorporates "
                    f"insights from current technical market trends, macroeconomic indicators, and "
                    f"social media sentiment. Use this plan as a foundation for evaluating your next "
                    f"trading decision.\n\n{feature_context}\n\nProposed Investment Plan: {investment_plan}\n\n"
                    f"Leverage these insights to make an informed and strategic decision.\n\n"
                    "First write your natural-language trading rationale. Then append a machine-readable "
                    "summary block in exactly this format:\n\n"
                    "STRUCTURED_SUMMARY\n"
                    "ACTION: <Buy|Hold|Sell>\n"
                    "REASONING: <one concise reasoning summary>\n"
                    "ENTRY_PRICE: <optional number>\n"
                    "STOP_LOSS: <optional number>\n"
                    "POSITION_SIZING: <optional sizing guidance>\n"
                    "END_STRUCTURED_SUMMARY\n\n"
                    "Keep the main rationale readable for humans. The summary block should be brief and only appear once at the end."
                ),
            },
        ]

        rendered_plan, structured_plan = invoke_structured_or_freetext_result(
            structured_llm,
            llm,
            messages,
            render_trader_proposal,
            "Trader",
            fallback=parse_trader_proposal,
        )
        trader_plan = (
            render_trader_proposal(structured_plan)
            if structured_plan is not None
            else rendered_plan
        )

        return {
            "messages": [AIMessage(content=trader_plan)],
            "trader_investment_plan": trader_plan,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
