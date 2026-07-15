"""Reddit search fetcher for ticker-specific discussion posts.

Uses Reddit's public JSON endpoints (``reddit.com/r/{sub}/search.json``)
which do not require an API key. Public throughput is ~10 requests per
minute per IP, well within budget for a single agent run that queries
a handful of finance subreddits per ticker.

Returns formatted plaintext blocks ready for prompt injection. Degrades
gracefully — returns a placeholder string rather than raising, so callers
never have to special-case missing data.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_API = "https://www.reddit.com/r/{sub}/search.json?{qs}"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"

# Default subreddits ordered roughly by signal density for ticker-specific
# discussion. wallstreetbets has the most volume but most noise; stocks /
# investing trend more measured. Caller can override.
DEFAULT_SUBREDDITS = ("wallstreetbets", "stocks", "investing")
CRYPTO_SUBREDDITS = (
    "CryptoCurrency",
    "CryptoMarkets",
    "Bitcoin",
    "ethereum",
    "ethfinance",
    "binance",
)

_CRYPTO_ALIASES = {
    "BTC": ("BTC", "Bitcoin"),
    "ETH": ("ETH", "Ethereum"),
    "SOL": ("SOL", "Solana"),
    "BNB": ("BNB", "Binance Coin"),
    "XRP": ("XRP", "Ripple"),
    "ADA": ("ADA", "Cardano"),
    "DOGE": ("DOGE", "Dogecoin"),
    "AVAX": ("AVAX", "Avalanche"),
    "DOT": ("DOT", "Polkadot"),
    "LINK": ("LINK", "Chainlink"),
    "LTC": ("LTC", "Litecoin"),
}


def _base_crypto_symbol(ticker: str) -> str:
    value = str(ticker or "").strip().upper()
    for suffix in ("-USD", "-USDT", "-USDC"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def reddit_search_terms(ticker: str) -> list[str]:
    """Return ticker/name aliases to improve crypto discussion recall."""
    raw = str(ticker or "").strip().upper()
    base = _base_crypto_symbol(raw)
    if base in _CRYPTO_ALIASES:
        terms = [base]
        terms.extend(_CRYPTO_ALIASES.get(base, ()))
        terms.append(raw)
    else:
        terms = [raw, base]
    return list(dict.fromkeys(term for term in terms if term))


def reddit_subreddits_for_ticker(ticker: str) -> tuple[str, ...]:
    """Add crypto-native subreddits for common crypto tickers."""
    base = _base_crypto_symbol(ticker)
    if base in _CRYPTO_ALIASES:
        return tuple(dict.fromkeys((*DEFAULT_SUBREDDITS, *CRYPTO_SUBREDDITS)))
    return DEFAULT_SUBREDDITS


def _fetch_subreddit(
    query: str,
    sub: str,
    limit: int,
    timeout: float,
    lookback_days: int,
) -> list[dict]:
    time_filter = "week"
    if lookback_days <= 1:
        time_filter = "day"
    elif lookback_days <= 30:
        time_filter = "month"
    elif lookback_days <= 365:
        time_filter = "year"
    qs = urlencode({
        "q": query,
        "restrict_sr": "on",
        "sort": "new",
        "t": time_filter,
        "limit": limit,
    })
    url = _API.format(sub=sub, qs=qs)
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning("Reddit fetch failed for r/%s · %s: %s", sub, query, exc)
        return []
    children = (payload.get("data") or {}).get("children") or []
    return [c.get("data", {}) for c in children if isinstance(c, dict)]


def fetch_reddit_posts(
    ticker: str,
    subreddits: Iterable[str] | None = None,
    limit_per_sub: int = 5,
    timeout: float = 10.0,
    inter_request_delay: float = 0.4,
    lookback_days: int = 7,
) -> str:
    """Fetch recent Reddit posts mentioning ``ticker`` across finance
    subreddits and return them as a formatted plaintext block.

    ``inter_request_delay`` keeps us under Reddit's public rate limit
    (~10 req/min per IP) even if the caller queries many subreddits.
    """
    terms = reddit_search_terms(ticker)
    subs = tuple(subreddits) if subreddits is not None else reddit_subreddits_for_ticker(ticker)
    blocks = []
    total_posts = 0
    seen_posts = set()
    for i, sub in enumerate(subs):
        if i > 0:
            time.sleep(inter_request_delay)
        posts = []
        for term in terms:
            posts.extend(_fetch_subreddit(term, sub, limit_per_sub, timeout, lookback_days))
            if len(posts) >= limit_per_sub:
                break
        deduped_posts = []
        for post in posts:
            key = post.get("permalink") or post.get("id") or post.get("url")
            if key in seen_posts:
                continue
            seen_posts.add(key)
            deduped_posts.append(post)
            if len(deduped_posts) >= limit_per_sub:
                break
        posts = deduped_posts
        total_posts += len(posts)
        if not posts:
            blocks.append(
                f"r/{sub}: <no posts found mentioning {ticker.upper()} "
                f"aliases={terms} in the past {lookback_days} days>"
            )
            continue

        lines = [f"r/{sub} — {len(posts)} recent posts mentioning {ticker.upper()} aliases={terms}:"]
        for p in posts:
            title = (p.get("title") or "").replace("\n", " ").strip()
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            created = p.get("created_utc")
            created_str = (
                time.strftime("%Y-%m-%d", time.gmtime(created)) if created else "?"
            )
            selftext = (p.get("selftext") or "").replace("\n", " ").strip()
            if len(selftext) > 240:
                selftext = selftext[:240] + "…"
            lines.append(
                f"  [{created_str} · {score:>4}↑ · {comments:>3}c] {title}"
                + (f"\n    body excerpt: {selftext}" if selftext else "")
            )
        blocks.append("\n".join(lines))

    if total_posts == 0:
        return (
            f"<no Reddit posts found mentioning {ticker.upper()} across "
            f"{', '.join(f'r/{s}' for s in subs)} using aliases={terms} "
            f"in the past {lookback_days} days>"
        )
    return "\n\n".join(blocks)
