"""API path compatibility aliases for the Workbench server."""

API_PATH_ALIASES = {
    "/api/observations": "/api/conclusions",
    "/api/observations/from-run": "/api/conclusions/from-run",
    "/api/observations/update": "/api/conclusions/update",
    "/api/observations/delete": "/api/conclusions/delete",
    "/api/simulation/forecast/account": "/api/paper/account",
    "/api/simulation/forecast/quote": "/api/paper/quote",
    "/api/simulation/forecast/signals": "/api/paper/signals",
    "/api/simulation/forecast/skills": "/api/paper/skills",
    "/api/simulation/forecast/analytics": "/api/paper/analytics",
    "/api/simulation/forecast/reset": "/api/paper/reset",
    "/api/simulation/forecast/order": "/api/paper/order",
    "/api/simulation/forecast/observe": "/api/forecast-observations",
    "/api/simulation/backtest/from-signal": "/api/paper/replay-signal",
    "/api/simulation/backtest/manual": "/api/paper/replay-manual",
    "/api/simulation/observation/intraday": "/api/paper/intraday",
    "/api/simulation/episodes": "/api/paper/episodes",
}


def canonical_api_path(path: str) -> str:
    lookup = str(path or "").rstrip("/")
    if not lookup:
        return path
    return API_PATH_ALIASES.get(lookup, path)
