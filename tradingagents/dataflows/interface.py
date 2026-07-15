from typing import Annotated
import sys
from requests import RequestException

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .akshare_cn import get_stock_data_cn, get_indicator_cn
from .baostock_cn import (
    get_stock_data_cn as get_stock_data_baostock_cn,
    get_indicator_cn as get_indicator_baostock_cn,
)
from .akshare_news_cn import (
    get_news_cn,
    get_global_news_cn,
    get_insider_transactions_cn,
)
from .akshare_fundamentals_cn import (
    get_fundamentals_cn,
    get_balance_sheet_cn,
    get_cashflow_cn,
    get_income_statement_cn,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from tradingagents.core.run_metrics import record_vendor_metric

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare_cn",
    "baostock_cn",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "akshare_cn": get_stock_data_cn,
        "baostock_cn": get_stock_data_baostock_cn,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "akshare_cn": get_indicator_cn,
        "baostock_cn": get_indicator_baostock_cn,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare_cn": get_fundamentals_cn,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare_cn": get_balance_sheet_cn,
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare_cn": get_cashflow_cn,
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare_cn": get_income_statement_cn,
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare_cn": get_news_cn,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare_cn": get_global_news_cn,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "akshare_cn": get_insider_transactions_cn,
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = _resolve_vendor_config(category, method, *args, **kwargs)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]
    symbol = _extract_symbol_arg(method, *args, **kwargs)

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl
        record_vendor_metric("attempt", method, vendor)
        _debug_vendor_trace(
            f"[vendor] method={method} symbol={symbol or '-'} trying={vendor}",
            level="debug",
        )

        try:
            result = impl_func(*args, **kwargs)
            if _should_fallback_on_result(vendor, result):
                record_vendor_metric("fallback", method, vendor)
                _debug_vendor_trace(
                    f"[vendor] method={method} symbol={symbol or '-'} fallback_from={vendor} result=empty_or_unavailable",
                    level="summary",
                )
                continue
            record_vendor_metric("success", method, vendor)
            _debug_vendor_trace(
                f"[vendor] method={method} symbol={symbol or '-'} success={vendor}",
                level="debug",
            )
            return result
        except Exception as exc:
            if _should_fallback(vendor, exc):
                record_vendor_metric("fallback", method, vendor)
                _debug_vendor_trace(
                    f"[vendor] method={method} symbol={symbol or '-'} fallback_from={vendor} error={type(exc).__name__}: {exc}",
                    level="summary",
                )
                continue
            record_vendor_metric("failure", method, vendor)
            raise

    record_vendor_metric("failure", method, "all")
    raise RuntimeError(f"No available vendor for '{method}'")


def _resolve_vendor_config(category: str, method: str, *args, **kwargs) -> str:
    """Resolve the vendor chain for a specific tool call."""
    explicit = get_vendor(category, method)
    symbol = _extract_symbol_arg(method, *args, **kwargs)
    if symbol and _is_cn_symbol(symbol) and method in {
        "get_stock_data",
        "get_indicators",
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_news",
        "get_insider_transactions",
    }:
        if method in {"get_stock_data", "get_indicators"}:
            return "akshare_cn,baostock_cn,yfinance"
        return "akshare_cn,yfinance"
    if method == "get_global_news" and _is_cn_symbol(symbol):
        return "akshare_cn,yfinance"
    return explicit


def _extract_symbol_arg(method: str, *args, **kwargs) -> str:
    """Extract the ticker-like symbol argument from a tool call."""
    if "symbol" in kwargs:
        return str(kwargs["symbol"])
    if "ticker" in kwargs:
        return str(kwargs["ticker"])
    if not args:
        return ""
    if method in {"get_stock_data", "get_indicators"}:
        return str(args[0])
    if method in {"get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement", "get_news", "get_insider_transactions"}:
        return str(args[0])
    return ""


def _is_cn_symbol(symbol: str) -> bool:
    """Return True when a symbol looks like a mainland China A-share ticker."""
    symbol_upper = str(symbol).upper()
    return symbol_upper.endswith(".SS") or symbol_upper.endswith(".SZ")


def _should_fallback(vendor: str, exc: Exception) -> bool:
    """Return True when a vendor error should trigger fallback."""
    message = str(exc)
    if vendor == "alpha_vantage":
        if isinstance(exc, AlphaVantageRateLimitError):
            return True
        if isinstance(exc, ValueError) and "ALPHA_VANTAGE_API_KEY" in message:
            return True
        return False
    if vendor == "akshare_cn":
        return (
            isinstance(exc, RequestException)
            or "Connection aborted" in message
            or "only supports .SS/.SZ tickers" in message
        )
    if vendor == "baostock_cn":
        return "only supports .SS/.SZ tickers" in message
    return False


def _debug_vendor_trace(message: str, level: str = "debug") -> None:
    """Emit vendor trace lines according to the configured verbosity."""
    trace_level = str(get_config().get("vendor_trace_level", "summary")).strip().lower()
    if trace_level == "debug":
        print(message, file=sys.stderr)
        return
    if trace_level == "summary" and level != "debug":
        print(message, file=sys.stderr)


def _should_fallback_on_result(vendor: str, result: object) -> bool:
    """Treat vendor placeholder strings as soft failures so fallback can continue."""
    if not isinstance(result, str):
        return False
    normalized = result.strip().lower()
    soft_markers = (
        "no data found",
        "data unavailable",
        "rate limited",
        "unavailable",
        "no fundamentals data found",
        "no balance sheet data found",
        "no cash flow data found",
        "no income statement data found",
        "no insider transactions data found",
        "<stocktwits unavailable",
        "<cn retail sentiment proxy unavailable>",
        "<cn forum / attention proxy unavailable>",
    )
    return any(marker in normalized for marker in soft_markers)
