from __future__ import annotations

from datetime import datetime

import pandas as pd


def _is_cn_equity(symbol: str) -> bool:
    """Return True when a ticker looks like a mainland China A-share symbol."""
    symbol_upper = symbol.upper()
    return symbol_upper.endswith(".SS") or symbol_upper.endswith(".SZ")


def _to_cn_code(symbol: str) -> str:
    """Convert Yahoo-style CN ticker to raw exchange code for AKShare."""
    return symbol.upper().split(".")[0]


def get_news_cn(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch A-share news data from AKShare for CN tickers."""
    if not _is_cn_equity(ticker):
        raise ValueError(f"AKShare CN news vendor only supports .SS/.SZ tickers, got {ticker}")
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare news fallback."
        ) from exc

    code = _to_cn_code(ticker)
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    try:
        df = ak.stock_news_em(symbol=code)
    except Exception as exc:
        return f"Error fetching CN news for {ticker} via AKShare: {exc}"

    if df is None or df.empty:
        return f"No CN news found for {ticker} between {start_date} and {end_date}"

    date_col = next((col for col in df.columns if "时间" in col or "日期" in col), None)
    title_col = next((col for col in df.columns if "标题" in col or "新闻标题" in col), None)
    content_col = next((col for col in df.columns if "内容" in col or "摘要" in col), None)
    source_col = next((col for col in df.columns if "来源" in col), None)
    link_col = next((col for col in df.columns if "链接" in col or "url" in col.lower()), None)

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt + pd.Timedelta(days=1))]

    if df.empty:
        return f"No CN news found for {ticker} between {start_date} and {end_date}"

    lines = []
    for _, row in df.head(20).iterrows():
        title = str(row.get(title_col, "No title")) if title_col else "No title"
        content = str(row.get(content_col, "") or "")
        source = str(row.get(source_col, "Unknown")) if source_col else "Unknown"
        link = str(row.get(link_col, "") or "") if link_col else ""
        lines.append(f"### {title} (source: {source})")
        if content and content != "nan":
            lines.append(content)
        if link and link != "nan":
            lines.append(f"Link: {link}")
        lines.append("")

    return f"## {ticker} CN News, from {start_date} to {end_date}:\n\n" + "\n".join(lines)


def get_global_news_cn(curr_date: str, look_back_days: int = 7, limit: int = 20) -> str:
    """Fetch China macro / market news using AKShare."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare global news fallback."
        ) from exc
    curr_dt = pd.to_datetime(curr_date)
    start_dt = curr_dt - pd.Timedelta(days=look_back_days)

    candidates = []
    for fetcher in (
        getattr(ak, "news_cctv", None),
        getattr(ak, "stock_info_global_cls", None),
    ):
        if fetcher is None:
            continue
        try:
            df = fetcher()
        except Exception:
            continue
        if df is not None and not df.empty:
            candidates.append(df)

    if not candidates:
        return f"No CN global news found for {curr_date}"

    df = pd.concat(candidates, ignore_index=True)
    date_col = next((col for col in df.columns if "时间" in col or "日期" in col), None)
    title_col = next((col for col in df.columns if "标题" in col or "内容" in col), None)
    source_col = next((col for col in df.columns if "来源" in col), None)

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df[(df[date_col] >= start_dt) & (df[date_col] <= curr_dt + pd.Timedelta(days=1))]

    if df.empty:
        return f"No CN global news found for {curr_date}"

    lines = []
    for _, row in df.head(limit).iterrows():
        title = str(row.get(title_col, "No title")) if title_col else "No title"
        source = str(row.get(source_col, "Unknown")) if source_col else "Unknown"
        lines.append(f"### {title} (source: {source})")
        lines.append("")

    return f"## China Market News, from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n" + "\n".join(lines)


def get_insider_transactions_cn(symbol: str) -> str:
    """Return a safe CN-specific downgrade for insider transactions."""
    if not _is_cn_equity(symbol):
        raise ValueError(f"AKShare CN insider vendor only supports .SS/.SZ tickers, got {symbol}")
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare insider fallback."
        ) from exc
    code = _to_cn_code(symbol)
    for fetcher in (
        getattr(ak, "stock_ggcg_em", None),
        getattr(ak, "stock_notice_report", None),
    ):
        if fetcher is None:
            continue
        try:
            if fetcher.__name__ == "stock_notice_report":
                df = fetcher(symbol=code)
            else:
                df = fetcher(symbol=code)
        except Exception:
            continue
        if df is not None and not df.empty:
            return f"# CN Shareholder / Corporate Actions for {symbol.upper()}\n\n" + df.head(20).to_csv(index=False)
    return (
        f"Shareholder increase/decrease or executive action data is unavailable for {symbol} "
        "in the current CN pipeline."
    )
