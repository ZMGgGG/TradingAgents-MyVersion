from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


@dataclass
class CNRetailProxyResult:
    retail_block: str
    forum_block: str
    source_status: dict[str, str] = field(default_factory=dict)
    source_sample_counts: dict[str, int] = field(default_factory=dict)
    source_errors: dict[str, str] = field(default_factory=dict)
    source_concentration: float = 0.0
    active_source_count: int = 0


def fetch_cn_retail_proxy_bundle(ticker: str) -> CNRetailProxyResult:
    """Fetch richer A-share retail/attention proxy blocks from AKShare."""
    try:
        import akshare as ak
    except ImportError:
        return CNRetailProxyResult(
            retail_block="<CN retail sentiment proxy unavailable>",
            forum_block="<CN forum / attention proxy unavailable>",
            source_status={},
            source_sample_counts={},
            source_errors={"akshare": "import_unavailable"},
        )

    code = ticker.upper().split(".")[0]
    retail_specs = [
        ("hot_rank_detail", getattr(ak, "stock_hot_rank_detail_em", None), True),
        ("comment_em", getattr(ak, "stock_comment_em", None), True),
    ]
    forum_specs = [
        ("hot_rank", getattr(ak, "stock_hot_rank_em", None), False),
        ("individual_notice", getattr(ak, "stock_individual_notice_report", None), True),
        ("notice_report", getattr(ak, "stock_notice_report", None), True),
    ]

    source_status: dict[str, str] = {}
    source_sample_counts: dict[str, int] = {}
    source_errors: dict[str, str] = {}

    retail_block = _build_proxy_block(
        code,
        retail_specs,
        source_status,
        source_sample_counts,
        source_errors,
        block_title="CN retail sentiment proxy",
    )
    forum_block = _build_proxy_block(
        code,
        forum_specs,
        source_status,
        source_sample_counts,
        source_errors,
        block_title="CN forum / attention proxy",
    )

    counts = [count for count in source_sample_counts.values() if count > 0]
    total = sum(counts)
    concentration = (max(counts) / total) if total > 0 else 0.0
    active_sources = sum(1 for count in counts if count > 0)

    return CNRetailProxyResult(
        retail_block=retail_block,
        forum_block=forum_block,
        source_status=source_status,
        source_sample_counts=source_sample_counts,
        source_errors=source_errors,
        source_concentration=round(concentration, 4),
        active_source_count=active_sources,
    )


def _build_proxy_block(
    code: str,
    specs: list[tuple[str, Callable | None, bool]],
    source_status: dict[str, str],
    source_sample_counts: dict[str, int],
    source_errors: dict[str, str],
    *,
    block_title: str,
) -> str:
    blocks: list[str] = []
    for name, fetcher, expects_symbol in specs:
        if fetcher is None:
            source_status[name] = "missing"
            source_sample_counts[name] = 0
            continue
        try:
            if expects_symbol:
                df = fetcher(symbol=code)
            else:
                df = fetcher()
                if isinstance(df, pd.DataFrame) and "代码" in df.columns:
                    df = df[df["代码"].astype(str) == code]
        except Exception as exc:
            source_status[name] = "error"
            source_sample_counts[name] = 0
            source_errors[name] = f"{type(exc).__name__}: {exc}"
            continue

        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            source_status[name] = "empty"
            source_sample_counts[name] = 0
            continue

        trimmed = df.head(10)
        source_status[name] = "ok"
        source_sample_counts[name] = len(trimmed)
        blocks.append(f"## {name}\n{trimmed.to_csv(index=False)}")

    if not blocks:
        return (
            "<CN retail sentiment proxy unavailable>"
            if "retail" in block_title.lower()
            else "<CN forum / attention proxy unavailable>"
        )

    return f"# {block_title}\n\n" + "\n\n".join(blocks)
