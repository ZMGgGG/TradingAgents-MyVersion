from __future__ import annotations

from datetime import datetime, timedelta

import baostock as bs
import pandas as pd
from stockstats import wrap

from .stockstats_utils import _clean_dataframe


def _is_cn_equity(symbol: str) -> bool:
    """Return True when a ticker looks like a mainland China A-share symbol."""
    symbol_upper = symbol.upper()
    return symbol_upper.endswith(".SS") or symbol_upper.endswith(".SZ")


def _to_bs_code(symbol: str) -> str:
    """Convert Yahoo-style CN ticker to BaoStock market.code form."""
    symbol_upper = symbol.upper()
    code = symbol_upper.split(".")[0]
    market = "sh" if symbol_upper.endswith(".SS") else "sz"
    return f"{market}.{code}"


def _login() -> None:
    """Login to BaoStock."""
    result = bs.login()
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {result.error_msg}")


def _logout() -> None:
    """Logout from BaoStock."""
    try:
        bs.logout()
    except Exception:
        pass


def _query_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Query CN OHLCV history from BaoStock."""
    _login()
    try:
        rs = bs.query_history_k_data_plus(
            _to_bs_code(symbol),
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",
        )
        if rs.error_code != "0":
            raise RuntimeError(f"BaoStock query failed: {rs.error_msg}")

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=rs.fields)
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        return _clean_dataframe(df)
    finally:
        _logout()


def get_stock_data_cn(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch A-share OHLCV data from BaoStock for CN tickers."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"BaoStock CN stock vendor only supports .SS/.SZ tickers, got {symbol}")

    df = _query_history(symbol, start_date, end_date)
    if df.empty:
        return f"No BaoStock CN stock data found for symbol '{symbol}' between {start_date} and {end_date}"

    csv_string = df.to_csv(index=False)
    header = f"# CN stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += "# Data retrieved from: BaoStock\n\n"
    return header + csv_string


def get_indicator_cn(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str:
    """Generate CN stock indicator windows using BaoStock-backed price history."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"BaoStock CN indicator vendor only supports .SS/.SZ tickers, got {symbol}")

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_dt - timedelta(days=look_back_days)
    df = _query_history(symbol, before.strftime("%Y-%m-%d"), curr_date)
    if df.empty:
        return (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            "BaoStock CN data unavailable.\n"
        )

    stats_df = wrap(df.copy())
    stats_df["Date"] = pd.to_datetime(stats_df["Date"], errors="coerce")
    stats_df = stats_df.dropna(subset=["Date"])
    stats_df["Date"] = stats_df["Date"].dt.strftime("%Y-%m-%d")
    stats_df[indicator]

    lines = []
    date_ptr = curr_dt
    while date_ptr >= before:
        date_key = date_ptr.strftime("%Y-%m-%d")
        rows = stats_df[stats_df["Date"] == date_key]
        if rows.empty:
            value = "N/A: Not a trading day (weekend or holiday)"
        else:
            raw = rows.iloc[0][indicator]
            value = "N/A" if pd.isna(raw) else str(raw)
        lines.append(f"{date_key}: {value}")
        date_ptr -= timedelta(days=1)

    return (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + "\n".join(lines)
    )
