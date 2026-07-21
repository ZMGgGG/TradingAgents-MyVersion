from copy import deepcopy
from typing import Dict, Optional

import tradingagents.default_config as default_config

# Use default config but allow it to be overridden
_config: Optional[Dict] = None


def initialize_config():
    """Initialize the configuration with default values."""
    global _config
    if _config is None:
        _config = deepcopy(default_config.DEFAULT_CONFIG)


def set_config(config: Dict):
    """Update the configuration with custom values.

    Dict-valued keys (e.g. ``data_vendors``) are merged one level deep so a
    partial update like ``{"data_vendors": {"core_stock_apis": "alpha_vantage"}}``
    keeps the other nested keys from the default; scalar keys are replaced.
    """
    global _config
    initialize_config()
    incoming = deepcopy(config)
    for key, value in incoming.items():
        if key == "tool_vendors" and value == {}:
            _config[key] = {}
        elif isinstance(value, dict) and isinstance(_config.get(key), dict):
            _config[key].update(value)
        else:
            _config[key] = value
    if "_current_ticker" in incoming:
        _apply_current_ticker_vendor_overrides(str(incoming.get("_current_ticker") or ""))


def _apply_current_ticker_vendor_overrides(ticker: str) -> None:
    """Keep legacy ticker-specific market vendor overrides in config."""
    if _config is None:
        return
    tool_vendors = _config.setdefault("tool_vendors", {})
    auto_chain = "akshare_cn,yfinance"
    if ticker.upper().endswith((".SS", ".SZ")):
        tool_vendors["get_stock_data"] = auto_chain
        tool_vendors["get_indicators"] = auto_chain
        return
    for method in ("get_stock_data", "get_indicators"):
        if tool_vendors.get(method) == auto_chain:
            tool_vendors.pop(method, None)


def get_config() -> Dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    return deepcopy(_config)


# Initialize with default config
initialize_config()
