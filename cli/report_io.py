from __future__ import annotations

import datetime
import json
from pathlib import Path

from cli.report_helpers import build_evidence_ledger_sections, build_structured_summary_status


def save_report_to_disk(final_state, ticker: str, save_path: Path):
    """Save complete analysis report to disk with organized subfolders."""
    save_path.mkdir(parents=True, exist_ok=True)
    sections = []

    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(final_state["sentiment_report"], encoding="utf-8")
        analyst_parts.append(("Sentiment Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
        analyst_parts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(final_state["fundamentals_report"], encoding="utf-8")
        analyst_parts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
            research_parts.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
            research_parts.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")
            research_parts.append(("Research Manager", debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## II. Research Team Decision\n\n{content}")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(final_state["trader_investment_plan"], encoding="utf-8")
        sections.append(f"## III. Trading Team Plan\n\n### Trader\n{final_state['trader_investment_plan']}")

    decisioning_parts = []
    if final_state.get("alpha_mining_result"):
        decisioning_parts.append(("QuantaAlpha Mining", final_state["alpha_mining_result"]))
    if final_state.get("factor_score"):
        decisioning_parts.append(("Factor Score", final_state["factor_score"]))
    if final_state.get("position_sizing"):
        decisioning_parts.append(("Position Sizing", final_state["position_sizing"]))
    if final_state.get("risk_gate_result"):
        decisioning_parts.append(("Risk Gate", final_state["risk_gate_result"]))
    if final_state.get("execution_plan"):
        decisioning_parts.append(("Execution Plan", final_state["execution_plan"]))
    if decisioning_parts:
        decisioning_dir = save_path / "3_decisioning"
        decisioning_dir.mkdir(exist_ok=True)
        decisioning_text = "\n\n".join(
            f"### {name}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
            for name, payload in decisioning_parts
        )
        (decisioning_dir / "decisioning.md").write_text(decisioning_text, encoding="utf-8")
        sections.append(f"## III-B. Stage Two Decisioning\n\n{decisioning_text}")

    if final_state.get("alpha_experience_summary"):
        alpha_dir = save_path / "3_alpha_experience"
        alpha_dir.mkdir(exist_ok=True)
        alpha_text = "### Alpha Experience Summary\n```json\n" + json.dumps(
            final_state["alpha_experience_summary"],
            ensure_ascii=False,
            indent=2,
        ) + "\n```"
        (alpha_dir / "alpha_experience.md").write_text(alpha_text, encoding="utf-8")
        sections.append(f"## III-C. Alpha Experience Summary\n\n{alpha_text}")

    evidence_parts = build_evidence_ledger_sections(final_state)
    if evidence_parts:
        evidence_dir = save_path / "3_evidence"
        evidence_dir.mkdir(exist_ok=True)
        evidence_text = "\n\n".join(
            f"### {name}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
            for name, payload in evidence_parts
        )
        (evidence_dir / "evidence_ledgers.md").write_text(evidence_text, encoding="utf-8")
        sections.append(f"## III-D. Evidence Ledgers\n\n{evidence_text}")

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(risk["aggressive_history"], encoding="utf-8")
            risk_parts.append(("Aggressive Analyst", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(risk["conservative_history"], encoding="utf-8")
            risk_parts.append(("Conservative Analyst", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
            risk_parts.append(("Neutral Analyst", risk["neutral_history"]))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")
            sections.append(f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{risk['judge_decision']}")

    header = f"# Trading Analysis Report: {ticker}\n\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    statuses = build_structured_summary_status(final_state)
    status_lines = "\n".join(f"- {agent}: {status}" for agent, status in statuses)
    status_section = f"## 0. Structured Summary Status\n\n{status_lines}\n\n"
    (save_path / "complete_report.md").write_text(
        header + status_section + "\n\n".join(sections),
        encoding="utf-8",
    )
    return save_path / "complete_report.md"


def append_backtest_summary_to_report(report_file: Path, summary_file: Path):
    if not report_file.exists() or not summary_file.exists():
        return
    report_text = report_file.read_text(encoding="utf-8")
    summary_text = summary_file.read_text(encoding="utf-8")
    merged = report_text.rstrip() + "\n\n---\n\n## VI. Backtest Summary\n\n" + summary_text + "\n"
    report_file.write_text(merged, encoding="utf-8")


def append_report_evaluation_to_report(report_file: Path, evaluation_file: Path):
    if not report_file.exists() or not evaluation_file.exists():
        return
    report_text = report_file.read_text(encoding="utf-8")
    evaluation_text = evaluation_file.read_text(encoding="utf-8")
    merged = report_text.rstrip() + "\n\n---\n\n## VI. Report Evaluation\n\n" + evaluation_text + "\n"
    report_file.write_text(merged, encoding="utf-8")
