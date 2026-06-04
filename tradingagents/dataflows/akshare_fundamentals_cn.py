from __future__ import annotations

import pandas as pd


def _is_cn_equity(symbol: str) -> bool:
    """Return True when a ticker looks like a mainland China A-share symbol."""
    symbol_upper = symbol.upper()
    return symbol_upper.endswith(".SS") or symbol_upper.endswith(".SZ")


def _to_cn_code(symbol: str) -> str:
    """Convert Yahoo-style CN ticker to raw exchange code for AKShare."""
    return symbol.upper().split(".")[0]


def get_fundamentals_cn(ticker: str, curr_date: str = None) -> str:
    """Fetch A-share fundamentals summary from AKShare."""
    if not _is_cn_equity(ticker):
        raise ValueError(f"AKShare CN fundamentals vendor only supports .SS/.SZ tickers, got {ticker}")
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is not installed. Install the project dependencies again so CN tickers can use the AKShare fundamentals fallback."
        ) from exc
    code = _to_cn_code(ticker)

    frames = []
    for fetcher in (
        getattr(ak, "stock_individual_info_em", None),
        getattr(ak, "stock_financial_analysis_indicator", None),
    ):
        if fetcher is None:
            continue
        try:
            df = fetcher(symbol=code)
        except Exception:
            continue
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return f"No CN fundamentals data found for symbol '{ticker}'"

    parts = [f"# CN Company Fundamentals for {ticker.upper()}"]
    for idx, df in enumerate(frames, start=1):
        parts.append("")
        parts.append(f"## Fundamentals block {idx}")
        parts.append(df.to_csv(index=False))
    return "\n".join(parts)


def _load_cn_financial_report(symbol: str, report_type: str) -> pd.DataFrame:
    """Load CN financial statement data from AKShare/Sina."""
    try:
        import akshare as ak
    except ImportError:
        return pd.DataFrame()
    try:
        df = ak.stock_financial_report_sina(stock=symbol, symbol=report_type)
    except TypeError:
        df = ak.stock_financial_report_sina(stock=symbol, symbol=report_type)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    return df


def get_balance_sheet_cn(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch CN balance-sheet data from AKShare/Sina."""
    if not _is_cn_equity(ticker):
        raise ValueError(f"AKShare CN fundamentals vendor only supports .SS/.SZ tickers, got {ticker}")
    code = _to_cn_code(ticker)
    df = _load_cn_financial_report(code, "资产负债表")
    if df.empty:
        return f"Balance sheet data unavailable in the CN AKShare pipeline for {ticker}."
    return f"# CN Balance Sheet for {ticker.upper()}\n\n" + df.to_csv(index=False)


def get_cashflow_cn(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch CN cash-flow data from AKShare/Sina."""
    if not _is_cn_equity(ticker):
        raise ValueError(f"AKShare CN fundamentals vendor only supports .SS/.SZ tickers, got {ticker}")
    code = _to_cn_code(ticker)
    df = _load_cn_financial_report(code, "现金流量表")
    if df.empty:
        return f"Cash flow data unavailable in the CN AKShare pipeline for {ticker}."
    return f"# CN Cash Flow for {ticker.upper()}\n\n" + df.to_csv(index=False)


def get_income_statement_cn(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch CN income-statement data from AKShare/Sina."""
    if not _is_cn_equity(ticker):
        raise ValueError(f"AKShare CN fundamentals vendor only supports .SS/.SZ tickers, got {ticker}")
    code = _to_cn_code(ticker)
    df = _load_cn_financial_report(code, "利润表")
    if df.empty:
        return f"Income statement data unavailable in the CN AKShare pipeline for {ticker}."
    return f"# CN Income Statement for {ticker.upper()}\n\n" + df.to_csv(index=False)
