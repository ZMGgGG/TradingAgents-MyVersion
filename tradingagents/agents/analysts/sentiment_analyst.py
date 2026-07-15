"""Sentiment analyst — multi-source sentiment analysis for a target ticker.

Previously named ``social_media_analyst``. Renamed and redesigned because
the old version had a prompt that demanded social-media analysis but the
only tool available was Yahoo Finance news — which led LLMs to fabricate
Reddit/X/StockTwits content under prompt pressure (verified live).

The redesigned agent pre-fetches three complementary data sources before
the LLM is invoked and injects them into the prompt as structured blocks:

  1. News headlines     — Yahoo Finance (institutional framing)
  2. StockTwits messages — retail-trader posts indexed by cashtag, with
                           user-labeled Bullish/Bearish sentiment tags
  3. Reddit posts        — r/wallstreetbets, r/stocks, r/investing

The agent defaults to deterministic pre-fetch; when source coverage is
degraded, it may expose a narrow news tool fallback to fill gaps.

See: https://github.com/TauricResearch/TradingAgents/issues/557
"""
from datetime import datetime
import re
import sys

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.schemas import parse_analyst_feature_summary
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_compact_report_instruction,
    get_news,
    get_language_instruction,
    get_time_context_from_state,
)
from tradingagents.content_discovery import discover_related_content
from tradingagents.content_discovery.planner import render_discovery_context
from tradingagents.dataflows.cn_retail_proxy import fetch_cn_retail_proxy_bundle
from tradingagents.dataflows.reddit import fetch_reddit_posts, reddit_subreddits_for_ticker
from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages


def _has_usable_sentiment_block(text: str) -> bool:
    if not isinstance(text, str):
        return False
    normalized = text.strip().lower()
    if not normalized:
        return False
    unavailable_markers = (
        "no news found",
        "error fetching news",
        "<stocktwits unavailable",
        "<no stocktwits messages found",
        "<no reddit posts found",
        "<cn retail sentiment proxy unavailable>",
        "<cn forum / attention proxy unavailable>",
        "unavailable",
    )
    return not any(marker in normalized for marker in unavailable_markers)


def _contains_future_dated_news(text: str, end_date: str) -> bool:
    if not isinstance(text, str):
        return False
    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return False
    for match in set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)):
        try:
            if datetime.strptime(match, "%Y-%m-%d") > end_dt:
                return True
        except ValueError:
            continue
    return False


def _derive_sentiment_quality(
    *,
    ticker: str,
    end_date: str,
    source_status: dict[str, str],
    news_block: str,
    source_sample_counts: dict[str, int],
    source_concentration: float,
) -> tuple[list[str], float]:
    flags: list[str] = []
    if source_status.get("news") != "ok":
        flags.append("news_unavailable")
    if source_status.get("stocktwits") != "ok":
        flags.append("social_unavailable")
    if source_status.get("reddit") != "ok":
        flags.append("forum_unavailable")
    if _contains_future_dated_news(news_block, end_date):
        flags.append("future_dated_news")
    if ticker.upper().endswith((".SS", ".SZ")) and source_status.get("news") == "ok":
        flags.append("cn_news_led_sentiment")
    if source_sample_counts.get("stocktwits_proxy_rows", 0) <= 1:
        flags.append("retail_proxy_sparse")
    if source_sample_counts.get("reddit_proxy_rows", 0) <= 1:
        flags.append("forum_proxy_sparse")
    if source_concentration >= 0.8:
        flags.append("source_concentration_high")

    quality_weight = 1.0
    penalties = {
        "news_unavailable": 0.35,
        "social_unavailable": 0.10,
        "forum_unavailable": 0.10,
        "future_dated_news": 0.25,
        "cn_news_led_sentiment": 0.10,
        "retail_proxy_sparse": 0.08,
        "forum_proxy_sparse": 0.08,
        "source_concentration_high": 0.10,
    }
    for flag in flags:
        quality_weight -= penalties.get(flag, 0.0)

    return flags, max(0.3, min(1.0, quality_weight))


def _build_sentiment_evidence_ledger(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    source_status: dict[str, str],
    source_coverage: float,
    quality_flags: list[str],
    quality_weight: float,
) -> dict:
    return {
        "ticker": ticker,
        "window": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "source_status": source_status,
        "source_coverage": round(source_coverage, 4),
        "quality_flags": quality_flags,
        "quality_weight": round(quality_weight, 4),
    }


def _count_proxy_rows(block: str) -> int:
    if not isinstance(block, str):
        return 0
    lines = [line for line in block.splitlines() if line.strip()]
    csv_rows = [line for line in lines if "," in line and not line.startswith("##")]
    if len(csv_rows) <= 1:
        stocktwits_rows = [line for line in lines if line.startswith("[") and " · @" in line]
        reddit_rows = [line for line in lines if line.lstrip().startswith("[") and "↑" in line and "c]" in line]
        return len(stocktwits_rows) + len(reddit_rows)
    return len(csv_rows) - 1


def _should_enable_sentiment_tools(source_status: dict[str, str], source_coverage: float) -> bool:
    # Social/forum fetches stay deterministic. The LLM only gets a narrow
    # news fallback when coverage is too sparse to contextualize sentiment.
    if source_coverage < 0.5:
        return True
    return source_status.get("news") != "ok"


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a sentiment report in a
    single LLM call.
    """

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        asset_type = state.get("asset_type", "stock")
        time_context = get_time_context_from_state(state)
        end_date = time_context.as_of_date
        start_date = time_context.news_start_date()
        lookback_days = time_context.analysis_lookback_days
        instrument_context = build_instrument_context(ticker, asset_type) + " " + time_context.to_prompt_string()
        is_cn_ticker = ticker.upper().endswith(".SS") or ticker.upper().endswith(".SZ")
        discovery = discover_related_content(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
            asset_type=state.get("asset_type", "stock"),
        )

        # Pre-fetch all three sources. Each fetcher degrades gracefully and
        # returns a string (no exceptions surface from here), so the LLM
        # always sees something — either real data or a clear placeholder.
        news_block = render_discovery_context(discovery)
        if is_cn_ticker:
            cn_proxy = fetch_cn_retail_proxy_bundle(ticker)
            stocktwits_block = cn_proxy.retail_block
            reddit_block = cn_proxy.forum_block
        else:
            cn_proxy = None
            stocktwits_block = fetch_stocktwits_messages(
                ticker,
                limit=30,
                lookback_days=lookback_days,
            )
            reddit_block = fetch_reddit_posts(
                ticker,
                subreddits=reddit_subreddits_for_ticker(ticker) if asset_type == "crypto" else None,
                lookback_days=lookback_days,
            )

        print(
            "[sentiment-prefetch] "
            f"ticker={ticker} "
            f"news={'ok' if _has_usable_sentiment_block(news_block) else 'empty'} "
            f"stocktwits={'ok' if _has_usable_sentiment_block(stocktwits_block) else 'empty'} "
            f"reddit={'ok' if _has_usable_sentiment_block(reddit_block) else 'empty'}",
            file=sys.stderr,
        )
        source_status = {
            "news": "ok" if _has_usable_sentiment_block(news_block) else "empty",
            "stocktwits": "ok" if _has_usable_sentiment_block(stocktwits_block) else "empty",
            "reddit": "ok" if _has_usable_sentiment_block(reddit_block) else "empty",
        }
        stocktwits_samples = (
            cn_proxy.source_sample_counts.get("hot_rank_detail", 0) + cn_proxy.source_sample_counts.get("comment_em", 0)
            if cn_proxy is not None
            else _count_proxy_rows(stocktwits_block)
        )
        reddit_samples = (
            cn_proxy.source_sample_counts.get("hot_rank", 0)
            + cn_proxy.source_sample_counts.get("individual_notice", 0)
            + cn_proxy.source_sample_counts.get("notice_report", 0)
            if cn_proxy is not None
            else _count_proxy_rows(reddit_block)
        )
        usable_sources = sum(
            [
                1 if _has_usable_sentiment_block(news_block) else 0,
                1 if _has_usable_sentiment_block(stocktwits_block) else 0,
                1 if _has_usable_sentiment_block(reddit_block) else 0,
            ]
        )
        source_coverage = usable_sources / 3.0
        quality_flags, quality_weight = _derive_sentiment_quality(
            ticker=ticker,
            end_date=end_date,
            source_status=source_status,
            news_block=news_block,
            source_sample_counts={
                "stocktwits_proxy_rows": stocktwits_samples,
                "reddit_proxy_rows": reddit_samples,
            },
            source_concentration=(cn_proxy.source_concentration if cn_proxy is not None else 0.0),
        )
        evidence_ledger = _build_sentiment_evidence_ledger(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            source_status=source_status,
            source_coverage=source_coverage,
            quality_flags=quality_flags,
            quality_weight=quality_weight,
        )
        evidence_ledger["source_sample_counts"] = {
            "stocktwits_proxy_rows": stocktwits_samples,
            "reddit_proxy_rows": reddit_samples,
        }
        use_tools = _should_enable_sentiment_tools(source_status, source_coverage)
        evidence_ledger["tool_fallback_enabled"] = use_tools
        if cn_proxy is not None:
            evidence_ledger["cn_proxy_source_status"] = cn_proxy.source_status
            evidence_ledger["cn_proxy_source_errors"] = cn_proxy.source_errors
            evidence_ledger["source_concentration"] = cn_proxy.source_concentration

        system_message = _build_system_message(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            news_block=news_block,
            stocktwits_block=stocktwits_block,
            reddit_block=reddit_block,
            is_cn_ticker=is_cn_ticker,
            is_crypto=asset_type == "crypto",
            source_coverage=source_coverage,
            source_status=source_status,
            quality_flags=quality_flags,
            quality_weight=quality_weight,
        )
        if use_tools:
            system_message += (
                "\n\nA controlled fallback tool is available because source coverage is degraded. "
                "Use `get_news` only if the pre-fetched news/social/forum blocks are insufficient. "
                "If tool results are already present in the message history, synthesize the final "
                "sentiment report instead of calling more tools."
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("user", "{discovery_context}"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(discovery_context=render_discovery_context(discovery))

        chain = prompt | (llm.bind_tools([get_news]) if use_tools else llm)
        result = chain.invoke(state["messages"])
        report = "" if getattr(result, "tool_calls", None) else result.content
        features = parse_analyst_feature_summary(report).model_dump() if report else {}

        return {
            "messages": [result],
            "sentiment_report": report,
            "sentiment_features": features,
            "sentiment_evidence_ledger": evidence_ledger,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
    is_cn_ticker: bool,
    is_crypto: bool,
    source_coverage: float,
    source_status: dict[str, str],
    quality_flags: list[str],
    quality_weight: float,
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    stocktwits_label = "StockTwits messages — retail-trader social platform indexed by cashtag"
    stocktwits_practice = (
        "**Read the StockTwits Bullish/Bearish ratio as a leading retail-sentiment signal.** "
        "A 70/30 bullish/bearish split is moderately bullish; ≥90/10 may indicate over-extension "
        "and contrarian risk; 50/50 is uncertainty. Sample size matters — base rates on the actual "
        "message count, not percentages alone."
    )
    lookback_days = max(1, (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days)
    reddit_label = f"Reddit posts — r/wallstreetbets, r/stocks, r/investing (past {lookback_days} days)"
    if is_cn_ticker:
        stocktwits_label = "CN social sentiment proxy — unavailable in current pipeline"
        reddit_label = "CN forum sentiment proxy — unavailable in current pipeline"
    if is_crypto:
        stocktwits_label = "StockTwits messages — optional crypto retail proxy indexed by cashtag"
        stocktwits_practice = (
            "**Use StockTwits as a secondary crypto retail proxy.** If it has enough messages, read "
            "the Bullish/Bearish ratio and message text as one input. If it is unavailable or sparse, "
            "mention the gap once, use plain wording such as 'retail social data is temporarily unavailable', "
            "and shift weight to Reddit, news, market structure, and derivatives evidence."
        )
        reddit_label = (
            f"Reddit posts — finance plus crypto-native communities "
            f"({', '.join('r/' + s for s in reddit_subreddits_for_ticker(ticker))}; past {lookback_days} days)"
        )
    cn_guidance = ""
    if is_cn_ticker:
        cn_guidance = """
## Mainland China ticker guidance

- For mainland China A-share tickers, global retail social sources like StockTwits and Reddit are not first-class inputs in this pipeline.
- If the CN social/forum proxy blocks are unavailable or sparse, you must still produce a useful sentiment judgment from the news framing and any available attention proxy.
- In that case, explicitly lower confidence, but do not conclude "no valid sentiment signal" merely because Western social platforms are absent.
- Use headline tone, repetition of narratives, policy framing, and any hot-rank / comment proxy as sentiment evidence.
- For mainland China tickers, company-specific news and local attention proxies should dominate your sentiment judgment. Do not over-weight missing Western social sources.
"""
    crypto_guidance = ""
    if is_crypto:
        crypto_guidance = """
## Crypto sentiment guidance

- For crypto assets, treat StockTwits/Reddit silence or API failure as missing evidence, not as proof that traders are accumulating, capitulating, or absent.
- StockTwits is an optional secondary source for crypto assets. Do not over-weight StockTwits failure, and do not list it repeatedly as a primary bearish or bullish reason.
- Prefer explicit crypto-native evidence such as actual BTC/ETH posts, funding/OI references, ETF-flow discussion, exchange-flow discussion, validator/staking discussion, or L2/DeFi activity.
- If source coverage is low, use neutral or low-confidence language and avoid strong claims about crowding, liquidation pressure, or "clean positioning" unless the provided text directly supports it.
- When output language is Chinese, describe missing provider data in user-friendly terms such as "暂不可用" or "样本不足"; avoid raw API-error wording unless it is necessary for auditability.
"""
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

## Source status

- News source availability: {source_status.get("news", "unknown")}
- Social source availability: {source_status.get("stocktwits", "unknown")}
- Forum source availability: {source_status.get("reddit", "unknown")}

Treat this source-status block as ground truth. Do not claim a source was unavailable if its status is marked `ok`. Do not say "all sources are unavailable" unless all three statuses are `empty`.

## Data-quality signals

- Quality flags: {", ".join(quality_flags) if quality_flags else "none"}
- Quality weight: {quality_weight:.2f}

Treat these as reliability constraints. If quality flags indicate sparse or future-dated sentiment evidence, lower confidence and discuss the limitation explicitly.

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past {lookback_days} days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### {stocktwits_label}
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### {reddit_label}
Community discussion. Engagement signal via upvote score and comment count. Subreddit character matters (r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term).

<start_of_reddit>
{reddit_block}
<end_of_reddit>

{cn_guidance}
{crypto_guidance}

## How to analyze this data (best practices)

1. {stocktwits_practice}

2. **Look for cross-source divergences.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious).

3. **Weight Reddit posts by engagement.** A 400-upvote / 200-comment thread reflects community attention; a 3-upvote post is noise. Read the body excerpts for context — the title alone often misleads.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this caveat explicitly. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

9. **Do not duplicate the News Analyst.** The News Analyst focuses on events and macro facts. Your job is to focus on how the market appears to feel and position around those facts: tone, crowd agreement or disagreement, narrative intensity, and attention concentration.

## Output

{get_compact_report_instruction()}

Produce a sentiment report covering, in order:

1. **Overall sentiment direction** — Bullish / Bearish / Neutral / Mixed — with a brief confidence note based on data quality and sample size.
2. **Source-by-source breakdown** — what each of news / StockTwits / Reddit is telling you, with specific evidence (cite message counts, ratios, notable posts).
3. **Divergences, alignments, and key narratives** across sources.
4. **Sentiment-specific interpretation** — explain what the tone, attention, and disagreement imply for trader behavior, distinct from a pure event summary.
5. **Catalysts and risks** surfaced by the data.
6. **Markdown table** at the end summarizing key sentiment signals, their direction, source, and supporting evidence.
7. After the full report, append exactly one machine-readable block in this format:

FEATURE_SUMMARY
SCORE: <value from -1.00 to 1.00>
CONFIDENCE: <value from 0.00 to 1.00>
KEY_SIGNAL: <concise sentiment signal>
RISK_FLAG: <main sentiment or data caveat>
SOURCE_COVERAGE: {source_coverage:.2f}
QUALITY_FLAGS: {" | ".join(quality_flags) if quality_flags else "none"}
QUALITY_WEIGHT: {quality_weight:.2f}
END_FEATURE_SUMMARY

{get_language_instruction()}"""


# ---------------------------------------------------------------------------
# Backwards-compatibility shim
# ---------------------------------------------------------------------------
def create_social_media_analyst(llm):
    """Deprecated alias for :func:`create_sentiment_analyst`.

    Kept so existing code that imports ``create_social_media_analyst``
    continues to work.

    .. deprecated::
        Import :func:`create_sentiment_analyst` directly instead.
    """


def _fetch_cn_sentiment_proxy(ticker: str) -> str:
    """Fetch A-share popularity / comment style sentiment proxies."""
    try:
        import akshare as ak
    except ImportError:
        return "<CN retail sentiment proxy unavailable>"
    code = ticker.upper().split(".")[0]
    blocks = []
    for fetcher in (
        getattr(ak, "stock_hot_rank_detail_em", None),
        getattr(ak, "stock_comment_em", None),
    ):
        if fetcher is None:
            continue
        try:
            df = fetcher(symbol=code)
        except Exception:
            continue
        if df is not None and not df.empty:
            blocks.append(df.head(10).to_csv(index=False))
    if not blocks:
        return "<CN retail sentiment proxy unavailable>"
    return "\n\n".join(blocks)


def _fetch_cn_forum_proxy(ticker: str) -> str:
    """Fetch A-share discussion proxies from AKShare ranking / notice data."""
    try:
        import akshare as ak
    except ImportError:
        return "<CN forum / attention proxy unavailable>"
    code = ticker.upper().split(".")[0]
    blocks = []
    for fetcher in (
        getattr(ak, "stock_hot_rank_em", None),
        getattr(ak, "stock_individual_notice_report", None),
    ):
        if fetcher is None:
            continue
        try:
            if fetcher.__name__ == "stock_individual_notice_report":
                df = fetcher(symbol=code)
            else:
                df = fetcher()
        except Exception:
            continue
        if df is not None and not df.empty:
            if "代码" in df.columns:
                df = df[df["代码"].astype(str) == code]
            blocks.append(df.head(10).to_csv(index=False))
    if not blocks:
        return "<CN forum / attention proxy unavailable>"
    return "\n\n".join(blocks)
    import warnings
    warnings.warn(
        "create_social_media_analyst is deprecated and will be removed in a "
        "future version. Use create_sentiment_analyst instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return create_sentiment_analyst(llm)
