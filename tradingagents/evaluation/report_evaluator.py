from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportEvaluation(BaseModel):
    factual_coverage: float = Field(ge=0.0, le=10.0)
    evidence_support: float = Field(ge=0.0, le=10.0)
    reasoning_consistency: float = Field(ge=0.0, le=10.0)
    risk_awareness: float = Field(ge=0.0, le=10.0)
    actionability: float = Field(ge=0.0, le=10.0)
    writing_quality: float = Field(ge=0.0, le=10.0)
    total_score: float = Field(ge=0.0, le=100.0)
    verdict: str
    missing_points: str
    unsupported_claims: str
    correction_plan: str
    prompt_tuning_notes: str


class ReportEvaluator:
    """Evaluate an LLM research report against a reference answer.

    This is intentionally a sidecar evaluator: it scores and critiques the
    saved report without changing the trading decision. The goal is to build
    a repeatable correction loop for report-quality training samples.
    """

    def __init__(self, llm: Any):
        self.llm = llm

    def evaluate(
        self,
        generated_report: str,
        reference_answer: str,
        topic: str = "",
    ) -> ReportEvaluation:
        prompt = self._build_prompt(generated_report, reference_answer, topic)
        response = self.llm.invoke(prompt)
        text = getattr(response, "content", str(response))
        return parse_report_evaluation(text)

    def evaluate_files(
        self,
        generated_report_path: Path,
        reference_answer_path: Path,
        topic: str = "",
    ) -> ReportEvaluation:
        generated_report = generated_report_path.read_text(encoding="utf-8")
        reference_answer = reference_answer_path.read_text(encoding="utf-8")
        return self.evaluate(generated_report, reference_answer, topic=topic)

    def _build_prompt(
        self,
        generated_report: str,
        reference_answer: str,
        topic: str,
    ) -> list[dict[str, str]]:
        topic_line = topic or "Unspecified investment research topic"
        return [
            {
                "role": "system",
                "content": (
                    "You are a strict investment research report evaluator. "
                    "Compare the generated report against the reference answer. "
                    "Score only what is supported by the reference and the report. "
                    "Do not reward fluent but unsupported claims. Return exactly "
                    "the EVALUATION_SUMMARY block requested by the user."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Topic:\n{topic_line}\n\n"
                    "Reference answer:\n"
                    f"{reference_answer}\n\n"
                    "Generated report:\n"
                    f"{generated_report}\n\n"
                    "Evaluate the generated report using 0-10 scores for each dimension. "
                    "Then compute TOTAL_SCORE as the average dimension score multiplied by 10.\n\n"
                    "Return this exact format:\n"
                    "EVALUATION_SUMMARY\n"
                    "FACTUAL_COVERAGE: <0-10>\n"
                    "EVIDENCE_SUPPORT: <0-10>\n"
                    "REASONING_CONSISTENCY: <0-10>\n"
                    "RISK_AWARENESS: <0-10>\n"
                    "ACTIONABILITY: <0-10>\n"
                    "WRITING_QUALITY: <0-10>\n"
                    "TOTAL_SCORE: <0-100>\n"
                    "VERDICT: <one concise paragraph>\n"
                    "MISSING_POINTS: <what the generated report missed>\n"
                    "UNSUPPORTED_CLAIMS: <claims that lack support or conflict with reference>\n"
                    "CORRECTION_PLAN: <specific revisions to improve the report>\n"
                    "PROMPT_TUNING_NOTES: <how to adjust prompts/data/features next time>\n"
                    "END_EVALUATION_SUMMARY"
                ),
            },
        ]


def render_report_evaluation(evaluation: ReportEvaluation) -> str:
    return "\n".join(
        [
            "# Research Report Evaluation",
            "",
            "## Scores",
            "",
            f"- Factual Coverage: {evaluation.factual_coverage:.1f}/10",
            f"- Evidence Support: {evaluation.evidence_support:.1f}/10",
            f"- Reasoning Consistency: {evaluation.reasoning_consistency:.1f}/10",
            f"- Risk Awareness: {evaluation.risk_awareness:.1f}/10",
            f"- Actionability: {evaluation.actionability:.1f}/10",
            f"- Writing Quality: {evaluation.writing_quality:.1f}/10",
            f"- Total Score: {evaluation.total_score:.1f}/100",
            "",
            "## Verdict",
            "",
            evaluation.verdict,
            "",
            "## Missing Points",
            "",
            evaluation.missing_points,
            "",
            "## Unsupported Claims",
            "",
            evaluation.unsupported_claims,
            "",
            "## Correction Plan",
            "",
            evaluation.correction_plan,
            "",
            "## Prompt Tuning Notes",
            "",
            evaluation.prompt_tuning_notes,
        ]
    )


def parse_report_evaluation(text: str) -> ReportEvaluation:
    block = _extract_evaluation_block(text)
    dimension_scores = {
        "factual_coverage": _field_float(block, "FACTUAL_COVERAGE"),
        "evidence_support": _field_float(block, "EVIDENCE_SUPPORT"),
        "reasoning_consistency": _field_float(block, "REASONING_CONSISTENCY"),
        "risk_awareness": _field_float(block, "RISK_AWARENESS"),
        "actionability": _field_float(block, "ACTIONABILITY"),
        "writing_quality": _field_float(block, "WRITING_QUALITY"),
    }
    fallback_total = sum(dimension_scores.values()) / len(dimension_scores) * 10.0
    return ReportEvaluation(
        **dimension_scores,
        total_score=_field_float(block, "TOTAL_SCORE", fallback_total, floor=0.0, ceiling=100.0),
        verdict=_field_text(block, "VERDICT") or "No verdict returned.",
        missing_points=_field_text(block, "MISSING_POINTS") or "No missing points returned.",
        unsupported_claims=_field_text(block, "UNSUPPORTED_CLAIMS") or "No unsupported claims returned.",
        correction_plan=_field_text(block, "CORRECTION_PLAN") or "No correction plan returned.",
        prompt_tuning_notes=_field_text(block, "PROMPT_TUNING_NOTES") or "No prompt tuning notes returned.",
    )


def _extract_evaluation_block(text: str) -> str:
    match = re.search(
        r"EVALUATION_SUMMARY\s*(.*?)\s*END_EVALUATION_SUMMARY",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else text.strip()


def _field_float(
    text: str,
    label: str,
    default: float = 0.0,
    floor: float = 0.0,
    ceiling: float = 10.0,
) -> float:
    value = _field_text(text, label)
    if not value:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return default
    return max(floor, min(ceiling, float(match.group(0))))


def _field_text(text: str, label: str) -> Optional[str]:
    pattern = rf"^{re.escape(label)}:\s*(.+?)(?=^[A-Z_]+:\s|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None
