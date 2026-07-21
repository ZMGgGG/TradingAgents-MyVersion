from __future__ import annotations

import re
from html import unescape
from pathlib import Path
import subprocess


def extract_reference_text_from_html_file(path: Path) -> str:
    """Extract a readable reference body from a saved local HTML report."""
    html = path.read_text(encoding="utf-8", errors="ignore")
    title = _extract_first(html, r"<title>(.*?)</title>") or path.stem
    description = _extract_first(
        html,
        r'<meta\s+name="description"\s+content="(.*?)"',
    ) or ""

    article = (
        _extract_first(html, r"<article\b.*?</article>")
        or _extract_first(html, r"<main\b.*?</main>")
        or _extract_first(html, r"<body\b.*?</body>")
        or html
    )

    cleaned = article
    cleaned = re.sub(r"(?is)<script\b.*?</script>", " ", cleaned)
    cleaned = re.sub(r"(?is)<style\b.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?is)<noscript\b.*?</noscript>", " ", cleaned)
    cleaned = re.sub(r"(?is)<svg\b.*?</svg>", " ", cleaned)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p\s*>", "\n\n", cleaned)
    cleaned = re.sub(r"(?i)</div\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</li\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)<li\b[^>]*>", "- ", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"(?m)^[ ]+", "", cleaned)
    cleaned = cleaned.strip()

    parts = [f"# {title}".strip()]
    if description:
        parts.extend(["", description.strip()])
    if cleaned:
        parts.extend(["", cleaned])
    return "\n".join(parts).strip() + "\n"


def extract_reference_text_from_pdf_file(path: Path) -> str:
    """Extract readable text from a local PDF reference.

    We prefer Python PDF readers when available and fall back to `strings`
    so the workflow still works in lean environments.
    """
    text = (
        _extract_pdf_with_pypdf(path)
        or _extract_pdf_with_pypdf2(path)
        or _extract_pdf_with_pdfplumber(path)
        or _extract_pdf_with_strings(path)
    )
    title = path.stem
    cleaned = _clean_plain_text(text)
    return f"# {title}\n\n{cleaned}\n"


def _extract_first(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1 if match.groups() else 0).strip()
    return None


def _extract_pdf_with_pypdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


def _extract_pdf_with_pypdf2(path: Path) -> str | None:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


def _extract_pdf_with_pdfplumber(path: Path) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        return None


def _extract_pdf_with_strings(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["/usr/bin/strings", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _clean_plain_text(text: str | None) -> str:
    if not text:
        return "PDF text extraction yielded no readable content."
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"(?m)^[ ]+", "", cleaned)
    return cleaned.strip() or "PDF text extraction yielded no readable content."
