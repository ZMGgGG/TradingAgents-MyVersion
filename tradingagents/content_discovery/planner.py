from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable

from tradingagents.dataflows.interface import route_to_vendor


DISCOVERY_CACHE_VERSION = "v2"


@dataclass
class ContentDiscoveryResult:
    ticker: str
    start_date: str
    end_date: str
    expanded_queries: list[str] = field(default_factory=list)
    company_blocks: list[str] = field(default_factory=list)
    related_blocks: list[str] = field(default_factory=list)
    macro_block: str = ""
    source_count: int = 0
    source_diversity: int = 0
    summary: str = ""


def discover_related_content(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
    asset_type: str = "stock",
) -> ContentDiscoveryResult:
    """Fetch ticker, related-theme, and macro content using simple query expansion."""
    cache_file = _discovery_cache_file(ticker, start_date, end_date, lookback_days, asset_type)
    cached = _load_discovery_cache(cache_file)
    if cached is not None:
        return cached

    expanded_queries = build_expanded_queries(ticker, asset_type=asset_type)
    company_blocks: list[str] = []
    related_blocks: list[str] = []

    primary_block = route_to_vendor("get_news", ticker, start_date, end_date)
    if _has_content(primary_block):
        company_blocks.append(primary_block)

    scored_related: list[tuple[int, str]] = []
    for query in expanded_queries:
        if query == ticker:
            continue
        try:
            block = _fetch_related_block(query, ticker, start_date, end_date)
        except Exception as exc:
            block = f"Error fetching related content for {query}: {exc}"
        if _has_content(block):
            scored_related.append((_query_relevance_score(query, ticker), block))

    related_blocks = _dedupe_blocks(
        [block for _score, block in sorted(scored_related, key=lambda item: item[0], reverse=True)]
    )

    try:
        macro_block = route_to_vendor("get_global_news", end_date, lookback_days, None)
    except Exception as exc:
        macro_block = f"Error fetching global news: {exc}"

    source_count = sum(1 for item in [*company_blocks, *related_blocks, macro_block] if _has_content(item))
    source_diversity = len({label for label, block in _iter_labeled_blocks(company_blocks, related_blocks, macro_block) if _has_content(block)})
    summary = (
        f"Expanded {ticker} into {len(expanded_queries)} related queries; "
        f"usable content blocks={source_count}, source_diversity={source_diversity}."
    )
    result = ContentDiscoveryResult(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        expanded_queries=expanded_queries,
        company_blocks=company_blocks,
        related_blocks=related_blocks,
        macro_block=macro_block,
        source_count=source_count,
        source_diversity=source_diversity,
        summary=summary,
    )
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_expanded_queries(ticker: str, asset_type: str = "stock") -> list[str]:
    """Generate simple deterministic related queries for the current instrument."""
    ticker_upper = ticker.upper()
    base_code = ticker_upper.split(".")[0]
    queries = [ticker_upper, base_code]

    if asset_type == "crypto":
        symbol = ticker_upper.replace("-USD", "").replace("-USDT", "").replace("-USDC", "")
        queries.extend([
            symbol,
            f"{symbol} crypto",
            f"{symbol} blockchain",
            f"{symbol} spot ETF flows",
            f"{symbol} funding rate open interest",
            f"{symbol} exchange inflows outflows",
        ])
        if symbol == "ETH":
            queries.extend([
                "Ethereum gas fees",
                "Ethereum staking withdrawals",
                "Ethereum Layer 2 TVL",
                "Ethereum ETF flows",
            ])
        elif symbol == "BTC":
            queries.extend([
                "Bitcoin ETF flows",
                "Bitcoin miner selling",
                "Bitcoin exchange reserves",
                "Bitcoin stablecoin inflows",
            ])
    elif ticker_upper.endswith((".SS", ".SZ")):
        aliases = _extract_cn_name_aliases(ticker_upper)
        queries.extend(aliases)
        queries.extend(
            [
                f"{base_code} 公告",
                f"{base_code} 业绩",
                f"{base_code} 行业",
                f"{base_code} 资金流",
                f"{base_code} 龙虎榜",
                f"{base_code} 概念",
                f"{base_code} 板块",
                f"{base_code} 研报",
            ]
        )
        for alias in aliases:
            queries.extend(
                [
                    f"{alias} 公告",
                    f"{alias} 业绩",
                    f"{alias} 板块",
                    f"{alias} 概念",
                ]
            )
    else:
        queries.extend(
            [
                f"{base_code} earnings",
                f"{base_code} guidance",
                f"{base_code} industry",
                f"{base_code} outlook",
            ]
        )

    return list(dict.fromkeys(query for query in queries if query))


def _fetch_related_block(query: str, ticker: str, start_date: str, end_date: str) -> str:
    """Route expanded queries to more appropriate A-share local proxies when possible."""
    if ticker.upper().endswith((".SS", ".SZ")):
        return _fetch_cn_related_block(query, ticker, start_date, end_date)
    return route_to_vendor("get_news", query, start_date, end_date)


def _fetch_cn_related_block(query: str, ticker: str, start_date: str, end_date: str) -> str:
    try:
        import akshare as ak
    except ImportError:
        return route_to_vendor("get_news", ticker, start_date, end_date)

    code = ticker.upper().split(".")[0]
    query_text = query.strip()

    if any(marker in query_text for marker in ("公告", "研报")):
        for fetcher in (
            getattr(ak, "stock_individual_notice_report", None),
            getattr(ak, "stock_notice_report", None),
        ):
            if fetcher is None:
                continue
            try:
                df = fetcher(symbol=code)
            except Exception:
                continue
            if df is not None and not df.empty:
                return f"## {query_text} related disclosure block\n\n" + df.head(10).to_csv(index=False)

    if any(marker in query_text for marker in ("龙虎榜", "资金流", "概念", "板块", "热度", "评论")):
        for fetcher in (
            getattr(ak, "stock_hot_rank_detail_em", None),
            getattr(ak, "stock_comment_em", None),
            getattr(ak, "stock_hot_rank_em", None),
        ):
            if fetcher is None:
                continue
            try:
                if fetcher.__name__ == "stock_hot_rank_em":
                    df = fetcher()
                    if "代码" in df.columns:
                        df = df[df["代码"].astype(str) == code]
                else:
                    df = fetcher(symbol=code)
            except Exception:
                continue
            if df is not None and not df.empty:
                return f"## {query_text} related retail proxy block\n\n" + df.head(10).to_csv(index=False)

    return route_to_vendor("get_news", ticker, start_date, end_date)


def _extract_cn_name_aliases(ticker: str) -> list[str]:
    """Best-effort extract CN company names / aliases from fundamentals text."""
    code = ticker.split(".")[0]
    cache_file = Path(".tradingagents/cache/cn_alias_cache.json")
    cache = _load_alias_cache(cache_file)
    if ticker in cache:
        return cache[ticker]
    try:
        payload = route_to_vendor("get_fundamentals", ticker, None)
    except Exception:
        return []
    if not isinstance(payload, str):
        return []

    aliases: list[str] = []
    for line in payload.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized.startswith("名称") or normalized.startswith("股票简称") or normalized.startswith("公司名称"):
            parts = normalized.replace("：", ":").split(":", 1)
            if len(parts) == 2:
                value = parts[1].strip()
                if value and value != code:
                    aliases.append(value)
    deduped = list(dict.fromkeys(alias for alias in aliases if alias))
    cache[ticker] = deduped
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return deduped


def render_discovery_context(result: ContentDiscoveryResult) -> str:
    lines = [
        f"Content discovery summary: {result.summary}",
        f"Expanded queries: {', '.join(result.expanded_queries)}",
        "",
    ]
    if result.company_blocks:
        lines.append("### Primary ticker/company content")
        lines.extend(result.company_blocks)
        lines.append("")
    if result.related_blocks:
        lines.append("### Related discovered content")
        lines.extend(result.related_blocks)
        lines.append("")
    if result.macro_block:
        lines.append("### Macro / market context")
        lines.append(result.macro_block)
    return "\n".join(lines)


def _query_relevance_score(query: str, ticker: str) -> int:
    score = 0
    base_code = ticker.split(".")[0].upper()
    query_upper = query.upper()
    if base_code in query_upper:
        score += 2
    for marker in ("公告", "业绩", "龙虎榜", "概念", "板块", "研报", "资金流"):
        if marker in query:
            score += 1
    return score


def _dedupe_blocks(blocks: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for block in blocks:
        key = block.strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(block)
    return deduped


def _load_alias_cache(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _discovery_cache_file(
    ticker: str,
    start_date: str,
    end_date: str,
    lookback_days: int,
    asset_type: str,
) -> Path:
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return Path(".tradingagents/cache/content_discovery") / f"{safe_ticker}_{start_date}_{end_date}_{lookback_days}_{asset_type}_{DISCOVERY_CACHE_VERSION}.json"


def _load_discovery_cache(path: Path) -> ContentDiscoveryResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return ContentDiscoveryResult(**payload)


def _has_content(text: str) -> bool:
    if not isinstance(text, str):
        return False
    normalized = text.strip().lower()
    if not normalized:
        return False
    return not (
        normalized.startswith("no news found")
        or normalized.startswith("error fetching")
        or normalized.startswith("no global news found")
    )


def _iter_labeled_blocks(
    company_blocks: Iterable[str],
    related_blocks: Iterable[str],
    macro_block: str,
) -> list[tuple[str, str]]:
    labeled = [("company", block) for block in company_blocks]
    labeled.extend(("related", block) for block in related_blocks)
    labeled.append(("macro", macro_block))
    return labeled
