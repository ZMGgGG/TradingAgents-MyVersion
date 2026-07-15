from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
import json
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


CRYPTO_BASE_SYMBOLS = {
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "ADA",
    "DOGE",
    "AVAX",
    "DOT",
    "LINK",
    "TRX",
    "TON",
    "MATIC",
    "LTC",
    "BCH",
    "UNI",
    "ATOM",
    "ETC",
    "FIL",
    "APT",
    "ARB",
    "OP",
    "SUI",
    "NEAR",
}

_BINANCE_FAPI = "https://fapi.binance.com"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"


def normalize_crypto_market_symbol(symbol: str) -> str:
    """Normalize common crypto tickers to a yfinance-compatible market symbol."""
    value = str(symbol or "").strip().upper()
    if not value:
        return value
    if value.endswith(("-USD", "-USDT", "-USDC")):
        return value
    if value in CRYPTO_BASE_SYMBOLS:
        return f"{value}-USD"
    return value


def _binance_perp_symbol(symbol: str) -> str | None:
    market_symbol = normalize_crypto_market_symbol(symbol)
    value = market_symbol.upper()
    for suffix in ("-USD", "-USDT", "-USDC"):
        if value.endswith(suffix):
            base = value[: -len(suffix)]
            return f"{base}USDT"
    if value in CRYPTO_BASE_SYMBOLS:
        return f"{value}USDT"
    return None


def _get_json(url: str, timeout: float = 4.0) -> Any:
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _safe_ratio_change(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    start = values[0]
    end = values[-1]
    if start == 0:
        return None
    return (end - start) / start


def _allows_current_derivatives_fallback(end: datetime) -> bool:
    """Only use live futures endpoints when they are close to the analysis date."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    analysis_day = end.replace(hour=0, minute=0, second=0, microsecond=0)
    return abs((today - analysis_day).days) <= 3


def _build_binance_derivatives_snapshot(symbol: str, end: datetime, lookback_days: int) -> dict[str, Any]:
    """Fetch public Binance USD-M futures metrics aligned to the analysis date."""
    perp_symbol = _binance_perp_symbol(symbol)
    if not perp_symbol:
        return {
            "available": False,
            "source": "binance_futures_public",
            "risk_flags": ["unsupported_binance_symbol"],
            "summary": "Binance futures snapshot unavailable: unsupported symbol.",
        }

    start = end - timedelta(days=max(lookback_days, 7))
    start_ms = _to_ms(start)
    end_ms = _to_ms(end + timedelta(days=1))
    risk_flags: list[str] = []
    errors: list[str] = []
    funding_rates: list[float] = []
    oi_values: list[float] = []
    long_short_ratios: list[float] = []
    current_fallback_used: list[str] = []
    current_fallback_reason = ""
    futures_quote_volume_24h = None
    futures_price_change_pct_24h = None

    try:
        qs = urlencode({
            "symbol": perp_symbol,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        })
        funding_payload = _get_json(f"{_BINANCE_FAPI}/fapi/v1/fundingRate?{qs}")
        if isinstance(funding_payload, list):
            for item in funding_payload:
                value = _safe_float(item.get("fundingRate"))
                if value is not None:
                    funding_rates.append(value)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        errors.append(f"funding_rate:{type(exc).__name__}")

    try:
        qs = urlencode({
            "symbol": perp_symbol,
            "period": "1d",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 30,
        })
        oi_payload = _get_json(f"{_BINANCE_FAPI}/futures/data/openInterestHist?{qs}")
        if isinstance(oi_payload, list):
            for item in oi_payload:
                value = _safe_float(item.get("sumOpenInterestValue") or item.get("sumOpenInterest"))
                if value is not None:
                    oi_values.append(value)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        errors.append(f"open_interest:{type(exc).__name__}")

    try:
        qs = urlencode({
            "symbol": perp_symbol,
            "period": "1d",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 30,
        })
        ls_payload = _get_json(f"{_BINANCE_FAPI}/futures/data/globalLongShortAccountRatio?{qs}")
        if isinstance(ls_payload, list):
            for item in ls_payload:
                value = _safe_float(item.get("longShortRatio"))
                if value is not None:
                    long_short_ratios.append(value)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        errors.append(f"long_short_ratio:{type(exc).__name__}")

    if _allows_current_derivatives_fallback(end):
        try:
            qs = urlencode({"symbol": perp_symbol})
            premium_payload = _get_json(f"{_BINANCE_FAPI}/fapi/v1/premiumIndex?{qs}")
            value = _safe_float(premium_payload.get("lastFundingRate")) if isinstance(premium_payload, dict) else None
            if value is not None and not funding_rates:
                funding_rates.append(value)
                current_fallback_used.append("current_funding_rate")
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            errors.append(f"current_funding_rate:{type(exc).__name__}")

        try:
            qs = urlencode({"symbol": perp_symbol})
            oi_payload = _get_json(f"{_BINANCE_FAPI}/fapi/v1/openInterest?{qs}")
            value = _safe_float(oi_payload.get("openInterest")) if isinstance(oi_payload, dict) else None
            if value is not None and not oi_values:
                oi_values.append(value)
                current_fallback_used.append("current_open_interest")
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            errors.append(f"current_open_interest:{type(exc).__name__}")

        try:
            qs = urlencode({"symbol": perp_symbol, "period": "1d", "limit": 1})
            ls_payload = _get_json(f"{_BINANCE_FAPI}/futures/data/globalLongShortAccountRatio?{qs}")
            if isinstance(ls_payload, list):
                for item in ls_payload:
                    value = _safe_float(item.get("longShortRatio"))
                    if value is not None and not long_short_ratios:
                        long_short_ratios.append(value)
                        current_fallback_used.append("current_long_short_ratio")
                        break
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            errors.append(f"current_long_short_ratio:{type(exc).__name__}")

        try:
            qs = urlencode({"symbol": perp_symbol})
            ticker_payload = _get_json(f"{_BINANCE_FAPI}/fapi/v1/ticker/24hr?{qs}")
            if isinstance(ticker_payload, dict):
                futures_quote_volume_24h = _safe_float(ticker_payload.get("quoteVolume"))
                futures_price_change_pct_24h = _safe_float(ticker_payload.get("priceChangePercent"))
                if futures_quote_volume_24h is not None or futures_price_change_pct_24h is not None:
                    current_fallback_used.append("current_24h_futures_ticker")
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            errors.append(f"current_24h_futures_ticker:{type(exc).__name__}")
    else:
        current_fallback_reason = "skipped: analysis date is not close enough to today for live futures endpoints"

    latest_funding = funding_rates[-1] if funding_rates else None
    avg_funding = sum(funding_rates) / len(funding_rates) if funding_rates else None
    oi_change = _safe_ratio_change(oi_values[-7:] if len(oi_values) >= 7 else oi_values)
    latest_long_short = long_short_ratios[-1] if long_short_ratios else None
    avg_long_short = sum(long_short_ratios) / len(long_short_ratios) if long_short_ratios else None

    if latest_funding is not None and abs(latest_funding) >= 0.0005:
        risk_flags.append("elevated_funding_rate")
    if oi_change is not None and abs(oi_change) >= 0.20:
        risk_flags.append("open_interest_changed_over_20pct")
    if latest_long_short is not None and (latest_long_short >= 2.0 or latest_long_short <= 0.5):
        risk_flags.append("crowded_long_short_ratio")
    available = bool(funding_rates or oi_values or long_short_ratios)
    if not available:
        risk_flags.append("derivatives_data_unavailable")
    if errors:
        risk_flags.append("derivatives_partial_error")

    return {
        "available": available,
        "source": "binance_futures_public",
        "perp_symbol": perp_symbol,
        "window": {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        },
        "funding_rate_latest": latest_funding,
        "funding_rate_average": avg_funding,
        "funding_sample_count": len(funding_rates),
        "open_interest_value_latest": oi_values[-1] if oi_values else None,
        "open_interest_change": oi_change,
        "open_interest_sample_count": len(oi_values),
        "long_short_ratio_latest": latest_long_short,
        "long_short_ratio_average": avg_long_short,
        "long_short_sample_count": len(long_short_ratios),
        "current_fallback_used": current_fallback_used,
        "current_fallback_reason": current_fallback_reason,
        "futures_quote_volume_24h": futures_quote_volume_24h,
        "futures_price_change_pct_24h": futures_price_change_pct_24h,
        "errors": errors,
        "risk_flags": risk_flags,
        "summary": (
            f"Binance futures snapshot for {perp_symbol}: "
            f"latest_funding={latest_funding if latest_funding is not None else 'n/a'}, "
            f"avg_funding={avg_funding if avg_funding is not None else 'n/a'}, "
            f"oi_change={_pct(oi_change)}, "
            f"latest_long_short={latest_long_short if latest_long_short is not None else 'n/a'}, "
            f"current_fallback={current_fallback_used or current_fallback_reason or 'not_needed'}, "
            f"samples=funding:{len(funding_rates)}/oi:{len(oi_values)}/long_short:{len(long_short_ratios)}, "
            f"risk_flags={risk_flags or ['none']}."
        ),
    }


def _parse_price_payload(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, str):
        return pd.DataFrame()
    csv_lines = [line for line in payload.splitlines() if line and not line.startswith("#")]
    if not csv_lines:
        return pd.DataFrame()
    try:
        df = pd.read_csv(StringIO("\n".join(csv_lines)))
    except Exception:
        return pd.DataFrame()
    if "Date" not in df.columns or "Close" not in df.columns:
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").set_index("Date")
    return df


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _window_return(close: pd.Series, periods: int) -> float | None:
    if len(close) <= periods:
        return None
    start = _safe_float(close.iloc[-periods - 1])
    end = _safe_float(close.iloc[-1])
    if start in (None, 0.0) or end is None:
        return None
    return (end - start) / start


def _max_drawdown(close: pd.Series) -> float | None:
    if close.empty:
        return None
    running_high = close.cummax()
    drawdowns = close / running_high - 1.0
    return _safe_float(drawdowns.min())


def build_crypto_market_snapshot(symbol: str, curr_date: str, lookback_days: int = 60) -> dict[str, Any]:
    """Build deterministic crypto-native price, volatility, and liquidity signals."""
    market_symbol = normalize_crypto_market_symbol(symbol)
    try:
        end = datetime.strptime(str(curr_date), "%Y-%m-%d")
    except ValueError:
        end = datetime.utcnow()
    start = end - timedelta(days=max(lookback_days + 10, 45))
    start_date = start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")

    try:
        payload = route_to_vendor("get_stock_data", market_symbol, start_date, end_date)
    except Exception as exc:
        return {
            "symbol": str(symbol),
            "market_symbol": market_symbol,
            "start_date": start_date,
            "end_date": end_date,
            "available": False,
            "summary": f"Crypto market snapshot unavailable for {market_symbol}: {type(exc).__name__}: {exc}",
            "risk_flags": ["price_data_vendor_error"],
        }
    df = _parse_price_payload(payload)
    if df.empty:
        return {
            "symbol": str(symbol),
            "market_symbol": market_symbol,
            "start_date": start_date,
            "end_date": end_date,
            "available": False,
            "summary": f"Crypto market snapshot unavailable for {market_symbol}: no OHLCV data returned.",
            "risk_flags": ["price_data_unavailable"],
        }

    close = df["Close"].dropna()
    volume = df["Volume"].dropna() if "Volume" in df.columns else pd.Series(dtype=float)
    latest_close = _safe_float(close.iloc[-1])
    return_7d = _window_return(close, 7)
    return_30d = _window_return(close, 30)
    daily_returns = close.pct_change().dropna().tail(30)
    realized_vol_30d = _safe_float(daily_returns.std() * (365 ** 0.5)) if not daily_returns.empty else None
    max_drawdown = _max_drawdown(close.tail(min(len(close), 60)))

    ema_10 = _safe_float(close.ewm(span=10, adjust=False).mean().iloc[-1]) if len(close) >= 10 else None
    ema_30 = _safe_float(close.ewm(span=30, adjust=False).mean().iloc[-1]) if len(close) >= 30 else None
    trend = "insufficient_data"
    if latest_close is not None and ema_10 is not None and ema_30 is not None:
        if latest_close > ema_10 > ema_30:
            trend = "uptrend"
        elif latest_close < ema_10 < ema_30:
            trend = "downtrend"
        else:
            trend = "range_or_transition"

    volume_ratio = None
    if len(volume) >= 30:
        avg_7 = _safe_float(volume.tail(7).mean())
        avg_30 = _safe_float(volume.tail(30).mean())
        if avg_7 is not None and avg_30 not in (None, 0.0):
            volume_ratio = avg_7 / avg_30

    derivatives_snapshot = _build_binance_derivatives_snapshot(market_symbol, end, min(max(lookback_days, 7), 30))

    risk_flags: list[str] = []
    if realized_vol_30d is not None and realized_vol_30d >= 0.90:
        risk_flags.append("high_annualized_volatility")
    if max_drawdown is not None and max_drawdown <= -0.20:
        risk_flags.append("large_recent_drawdown")
    if volume_ratio is not None and volume_ratio < 0.70:
        risk_flags.append("weak_recent_liquidity")
    if len(df) < 20:
        risk_flags.append("short_price_history")
    for flag in derivatives_snapshot.get("risk_flags", []):
        if flag not in risk_flags:
            risk_flags.append(flag)

    volume_ratio_text = f"{volume_ratio:.2f}" if volume_ratio is not None else "n/a"

    return {
        "symbol": str(symbol),
        "market_symbol": market_symbol,
        "start_date": start_date,
        "end_date": end_date,
        "available": True,
        "records": int(len(df)),
        "latest_close": latest_close,
        "return_7d": return_7d,
        "return_30d": return_30d,
        "realized_vol_30d": realized_vol_30d,
        "max_drawdown_60d": max_drawdown,
        "volume_7d_vs_30d": volume_ratio,
        "trend_regime": trend,
        "risk_flags": risk_flags,
        "derivatives_snapshot": derivatives_snapshot,
        "summary": (
            f"{market_symbol} crypto snapshot: trend={trend}, close={latest_close}, "
            f"7d_return={_pct(return_7d)}, 30d_return={_pct(return_30d)}, "
            f"30d_realized_vol={_pct(realized_vol_30d)}, "
            f"60d_max_drawdown={_pct(max_drawdown)}, "
            f"volume_7d_vs_30d={volume_ratio_text}, "
            f"derivatives_available={derivatives_snapshot.get('available')}, "
            f"risk_flags={risk_flags or ['none']}."
        ),
    }


def format_crypto_market_snapshot(snapshot: dict[str, Any]) -> str:
    """Render the crypto snapshot as a compact prompt block."""
    lines = [
        f"Crypto Market Snapshot for {snapshot.get('symbol')} ({snapshot.get('market_symbol')})",
        f"- Window: {snapshot.get('start_date')} to {snapshot.get('end_date')}",
        f"- Available: {snapshot.get('available')}",
    ]
    if not snapshot.get("available"):
        lines.append(f"- Summary: {snapshot.get('summary')}")
        lines.append(f"- Risk flags: {', '.join(snapshot.get('risk_flags', [])) or 'none'}")
        return "\n".join(lines)

    lines.extend(
        [
            f"- Records: {snapshot.get('records')}",
            f"- Latest close: {snapshot.get('latest_close')}",
            f"- 7d return: {_pct(snapshot.get('return_7d'))}",
            f"- 30d return: {_pct(snapshot.get('return_30d'))}",
            f"- 30d realized volatility: {_pct(snapshot.get('realized_vol_30d'))}",
            f"- 60d max drawdown: {_pct(snapshot.get('max_drawdown_60d'))}",
            f"- 7d/30d volume ratio: {snapshot.get('volume_7d_vs_30d') if snapshot.get('volume_7d_vs_30d') is not None else 'n/a'}",
            f"- Trend regime: {snapshot.get('trend_regime')}",
            f"- Risk flags: {', '.join(snapshot.get('risk_flags', [])) or 'none'}",
        ]
    )
    derivatives = snapshot.get("derivatives_snapshot") or {}
    if derivatives:
        lines.extend(
            [
                "- Derivatives snapshot:",
                f"  - Source: {derivatives.get('source')}",
                f"  - Perp symbol: {derivatives.get('perp_symbol', 'n/a')}",
                f"  - Available: {derivatives.get('available')}",
                f"  - Latest funding rate: {_pct(derivatives.get('funding_rate_latest'))}",
                f"  - Average funding rate: {_pct(derivatives.get('funding_rate_average'))}",
                f"  - Open interest change: {_pct(derivatives.get('open_interest_change'))}",
                f"  - Latest long/short ratio: {derivatives.get('long_short_ratio_latest') if derivatives.get('long_short_ratio_latest') is not None else 'n/a'}",
                f"  - 24h futures quote volume: {derivatives.get('futures_quote_volume_24h') if derivatives.get('futures_quote_volume_24h') is not None else 'n/a'}",
                f"  - 24h futures price change pct: {derivatives.get('futures_price_change_pct_24h') if derivatives.get('futures_price_change_pct_24h') is not None else 'n/a'}%",
                f"  - Current fallback: {', '.join(derivatives.get('current_fallback_used', [])) or derivatives.get('current_fallback_reason') or 'not needed'}",
                f"  - Sample counts: funding={derivatives.get('funding_sample_count', 0)}, open_interest={derivatives.get('open_interest_sample_count', 0)}, long_short={derivatives.get('long_short_sample_count', 0)}",
                f"  - Unavailable fields: {', '.join(derivatives.get('errors', [])) or 'none'}",
            ]
        )
    return "\n".join(lines)


@tool
def get_crypto_market_snapshot(
    symbol: Annotated[str, "crypto symbol or pair, e.g. BTC, BTC-USD, ETH-USDT"],
    curr_date: Annotated[str, "Current analysis date in yyyy-mm-dd format"],
    lookback_days: Annotated[int, "How many days of history to summarize"] = 60,
) -> str:
    """Return crypto-native trend, volatility, drawdown, and liquidity signals."""
    snapshot = build_crypto_market_snapshot(symbol, curr_date, lookback_days)
    return format_crypto_market_snapshot(snapshot)
