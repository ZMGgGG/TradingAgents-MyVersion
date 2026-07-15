from __future__ import annotations


def _summary_block_status(text: str) -> str:
    if not text or not isinstance(text, str):
        return "missing"
    if "STRUCTURED_SUMMARY" in text and "END_STRUCTURED_SUMMARY" in text:
        return "present"
    return "absent"


def build_structured_summary_status(final_state) -> list[tuple[str, str]]:
    statuses = []

    debate = final_state.get("investment_debate_state", {})
    risk = final_state.get("risk_debate_state", {})

    statuses.append(("Bull Researcher", _summary_block_status(debate.get("bull_history", ""))))
    statuses.append(("Bear Researcher", _summary_block_status(debate.get("bear_history", ""))))
    statuses.append(("Research Manager", _summary_block_status(debate.get("judge_decision", ""))))
    statuses.append(("Trader", _summary_block_status(final_state.get("trader_investment_plan", ""))))
    statuses.append(("Aggressive Analyst", _summary_block_status(risk.get("aggressive_history", ""))))
    statuses.append(("Conservative Analyst", _summary_block_status(risk.get("conservative_history", ""))))
    statuses.append(("Neutral Analyst", _summary_block_status(risk.get("neutral_history", ""))))
    statuses.append(("Portfolio Manager", _summary_block_status(risk.get("judge_decision", ""))))

    return statuses


def build_evidence_ledger_sections(final_state) -> list[tuple[str, dict]]:
    sections = []
    if final_state.get("market_evidence_ledger"):
        sections.append(("Market Evidence Ledger", final_state["market_evidence_ledger"]))
    if final_state.get("sentiment_evidence_ledger"):
        sections.append(("Sentiment Evidence Ledger", final_state["sentiment_evidence_ledger"]))
    if final_state.get("news_evidence_ledger"):
        sections.append(("News Evidence Ledger", final_state["news_evidence_ledger"]))
    if final_state.get("fundamentals_evidence_ledger"):
        sections.append(("Fundamentals Evidence Ledger", final_state["fundamentals_evidence_ledger"]))
    return sections
