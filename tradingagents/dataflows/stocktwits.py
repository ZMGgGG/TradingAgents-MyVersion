"""StockTwits public symbol-stream fetcher.

StockTwits exposes a per-symbol message stream at
``api.stocktwits.com/api/2/streams/symbol/{ticker}.json`` that requires no
API key, no OAuth, and no registration. Each message includes a
user-labeled sentiment field (``Bullish``/``Bearish``/null), the message
body, timestamp, and posting user.

The function is deliberately self-contained: short timeout, graceful
degradation on any HTTP or parse failure, and a string return type so
the calling agent gets a uniform interface regardless of whether the
network call succeeded.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"

_CRYPTO_STOCKTWITS_ALIASES = {
    "BTC": ("BTC.X", "BTC"),
    "ETH": ("ETH.X", "ETH"),
    "SOL": ("SOL.X", "SOL"),
    "BNB": ("BNB.X", "BNB"),
    "XRP": ("XRP.X", "XRP"),
    "ADA": ("ADA.X", "ADA"),
    "DOGE": ("DOGE.X", "DOGE"),
    "AVAX": ("AVAX.X", "AVAX"),
    "DOT": ("DOT.X", "DOT"),
    "LINK": ("LINK.X", "LINK"),
    "LTC": ("LTC.X", "LTC"),
}


def stocktwits_symbol_candidates(ticker: str) -> list[str]:
    """Return StockTwits symbols to try, including crypto cashtag aliases."""
    raw = str(ticker or "").strip().upper()
    if not raw:
        return []
    base = raw
    for suffix in ("-USD", "-USDT", "-USDC"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    candidates = list(_CRYPTO_STOCKTWITS_ALIASES.get(base, ()))
    candidates.extend([raw, base])
    return list(dict.fromkeys(c for c in candidates if c))


def fetch_stocktwits_messages(
    ticker: str,
    limit: int = 30,
    timeout: float = 10.0,
    lookback_days: int = 7,
) -> str:
    """Fetch recent StockTwits messages for ``ticker`` and return them as a
    formatted plaintext block ready for prompt injection.

    Returns a placeholder string when the endpoint is unreachable, the
    symbol has no messages, or the response shape is unexpected — the
    caller never has to special-case None or exceptions.
    """
    candidates = stocktwits_symbol_candidates(ticker)
    last_error = ""
    data = None
    used_symbol = candidates[0] if candidates else str(ticker).upper()

    for candidate in candidates:
        url = _API.format(ticker=candidate)
        req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            used_symbol = candidate
            break
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
            last_error = type(exc).__name__
            logger.warning("StockTwits fetch failed for %s via %s: %s", ticker, candidate, exc)

    if data is None:
        return (
            f"<stocktwits unavailable optional retail source for {ticker.upper()} "
            f"aliases={candidates}: {last_error or 'unknown'}; "
            "do not treat this as a directional sentiment signal>"
        )

    messages = data.get("messages", []) if isinstance(data, dict) else []
    if not messages:
        return f"<no StockTwits messages found for ${ticker.upper()} aliases={candidates}>"

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))
    lines = []
    bullish = bearish = unlabeled = 0
    kept = 0
    for m in messages:
        created = m.get("created_at", "")
        user = (m.get("user") or {}).get("username", "?")
        entities = m.get("entities") or {}
        sentiment_obj = entities.get("sentiment") or {}
        sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
        try:
            created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except Exception:
            created_dt = None
        if created_dt is not None and created_dt < cutoff:
            continue
        body = (m.get("body") or "").replace("\n", " ").strip()
        if len(body) > 280:
            body = body[:280] + "…"

        if sentiment == "Bullish":
            bullish += 1
            tag = "Bullish"
        elif sentiment == "Bearish":
            bearish += 1
            tag = "Bearish"
        else:
            unlabeled += 1
            tag = "no-label"
        lines.append(f"[{created} · @{user} · {tag}] {body}")
        kept += 1
        if kept >= limit:
            break

    total = bullish + bearish + unlabeled
    if total == 0:
        return f"<no StockTwits messages found for ${ticker.upper()} aliases={candidates} in the past {lookback_days} days>"
    bull_pct = round(100 * bullish / total) if total else 0
    bear_pct = round(100 * bearish / total) if total else 0
    summary = (
        f"StockTwits symbol used: ${used_symbol} · "
        f"Bullish: {bullish} ({bull_pct}%) · "
        f"Bearish: {bearish} ({bear_pct}%) · "
        f"Unlabeled: {unlabeled} · "
        f"Total: {total} messages in the past {lookback_days} days"
    )
    return summary + "\n\n" + "\n".join(lines)
