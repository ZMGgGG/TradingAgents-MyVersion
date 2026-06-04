from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from stockstats import wrap

from .stockstats_utils import _clean_dataframe


def _is_cn_equity(symbol: str) -> bool:
    """Return True when a ticker looks like a mainland China A-share symbol."""
    symbol_upper = symbol.upper()
    return symbol_upper.endswith(".SS") or symbol_upper.endswith(".SZ")


def _to_cn_code(symbol: str) -> str:
    """Convert Yahoo-style CN ticker to raw exchange code for AKShare."""
    return symbol.upper().split(".")[0]


def _load_cn_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Load CN OHLCV data from AKShare up to curr_date."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"AKShare CN stock vendor only supports .SS/.SZ tickers, got {symbol}")
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare fallback."
        ) from exc

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=365 * 2)
    code = _to_cn_code(symbol)
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=curr_dt.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return pd.DataFrame()

    rename_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
    }
    df = df.rename(columns=rename_map)
    keep_cols = [col for col in ["Date", "Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    df = _clean_dataframe(df[keep_cols])
    df = df[df["Date"] <= pd.to_datetime(curr_date)]
    return df


def _get_stock_stats_bulk_cn(symbol: str, indicator: str, curr_date: str) -> dict:
    """Calculate stockstats indicators from AKShare OHLCV data."""
    data = _load_cn_ohlcv(symbol, curr_date)
    if data.empty:
        return {}

    df = wrap(data.copy())
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df[indicator]

    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)
    return result_dict


def get_stock_data_cn(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch A-share OHLCV data from AKShare for CN tickers."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"AKShare CN stock vendor only supports .SS/.SZ tickers, got {symbol}")
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare fallback."
        ) from exc

    code = _to_cn_code(symbol)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return f"No AKShare CN stock data found for symbol '{symbol}' between {start_date} and {end_date}"

    rename_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
    }
    df = df.rename(columns=rename_map)
    keep_cols = [col for col in ["Date", "Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    df = _clean_dataframe(df[keep_cols])
    csv_string = df.to_csv(index=False)
    header = f"# CN stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += "# Data retrieved from: AKShare\n\n"
    return header + csv_string


def get_indicator_cn(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str:
    """Generate CN stock indicator windows using AKShare-backed price history."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"AKShare CN indicator vendor only supports .SS/.SZ tickers, got {symbol}")

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_dt - timedelta(days=look_back_days)
    indicator_data = _get_stock_stats_bulk_cn(symbol, indicator, curr_date)
    if not indicator_data:
        return (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            "AKShare CN data unavailable.\n"
        )

    lines = []
    date_ptr = curr_dt
    while date_ptr >= before:
        date_key = date_ptr.strftime("%Y-%m-%d")
        lines.append(f"{date_key}: {indicator_data.get(date_key, 'N/A: Not a trading day (weekend or holiday)')}")
        date_ptr -= timedelta(days=1)

    return (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + "\n".join(lines)
    )
