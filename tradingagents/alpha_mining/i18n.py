from __future__ import annotations

from tradingagents.dataflows.config import get_config


def alpha_language() -> str:
    """Return a compact language code for alpha-mining display text."""
    output_language = str(get_config().get("output_language", "English")).strip().lower()
    if output_language in {"chinese", "中文", "zh", "zh-cn", "zh_hans"}:
        return "zh"
    return "en"


def alpha_text(english: str, chinese: str) -> str:
    """Select localized alpha-mining text based on the configured output language."""
    return chinese if alpha_language() == "zh" else english
