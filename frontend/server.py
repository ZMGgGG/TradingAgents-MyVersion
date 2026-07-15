from __future__ import annotations

import datetime
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from tradingagents.alpha_mining import (
    AlphaCandidate,
    AlphaEvaluator,
    AlphaMiningEpisode,
    AlphaMiningHistory,
    AlphaRegistry,
    AlphaRegistryEntry,
    QuantaAlphaMiner,
    build_alpha_experience_summary,
    generate_crossover_set,
    generate_mutation_set,
)
from tradingagents.backtesting import BacktestScenario
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.evaluation import (
    ReportEvaluator,
    extract_reference_text_from_html_file,
    extract_reference_text_from_pdf_file,
    render_report_evaluation,
)
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.backtesting.engine import BacktestResult
from tradingagents.agents.schemas import parse_pm_decision
from tradingagents.core.run_metrics import (
    RunMetricsCallbackHandler,
    bind_run_metrics_collector,
)
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
from tradingagents.graph.checkpointer import clear_checkpoint, has_checkpoint


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
RUNS: dict[str, dict[str, Any]] = {}
RUN_CONCURRENCY = max(1, int(os.environ.get("TRADINGAGENTS_WORKBENCH_CONCURRENCY", "3")))
RUN_USER_CONCURRENCY = max(1, int(os.environ.get("TRADINGAGENTS_WORKBENCH_USER_CONCURRENCY", "2")))
RUN_SLOT = threading.Semaphore(RUN_CONCURRENCY)
USER_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
PERSISTED_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "stale"}

STRUCTURED_SUMMARY_LABELS = {
    "STRUCTURED_SUMMARY": "结构化摘要",
    "END_STRUCTURED_SUMMARY": "结构化摘要结束",
    "STANCE": "立场",
    "SCORE": "评分",
    "CONFIDENCE": "置信度",
    "EVIDENCE_QUALITY": "证据质量",
    "TIME_HORIZON_DAYS": "时间周期(天)",
    "THESIS": "核心论点",
    "REBUTTAL": "反驳要点",
    "KEY_RISKS": "关键风险",
    "RISK_POSTURE": "风险姿态",
    "MAX_POSITION_SIZE": "最大仓位",
    "STOP_LOSS": "止损",
    "TAKE_PROFIT": "止盈",
    "INVESTMENT_THESIS": "投资论点",
}

STANCE_LABELS = {
    "Bullish": "看多",
    "Bearish": "看空",
    "Neutral": "中性",
    "Aggressive": "激进",
    "Conservative": "保守",
}

CRYPTO_TICKERS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
    "MATIC", "LTC", "BCH", "UNI", "ATOM", "ETC", "FIL", "APT", "ARB", "OP",
}

OPENAI_COMPATIBLE_DISCOVERY_PROVIDERS = {
    "openai", "xai", "deepseek", "qwen", "qwen-cn", "glm", "glm-cn",
    "minimax", "minimax-cn", "openrouter", "ollama", "azure",
}
AUTH_COOKIE_NAME = "ta_workbench_session"
AUTH_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
AUTH_CHALLENGE_TTL_SECONDS = 5 * 60
AUTH_FAILED_LOGIN_LIMIT = 5
AUTH_LOCKOUT_SECONDS = 5 * 60
AUTH_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
AUTH_LOCK = threading.RLock()


def _looks_like_crypto_ticker(ticker: str) -> bool:
    symbol = str(ticker or "").strip().upper()
    return (
        symbol in CRYPTO_TICKERS
        or symbol.endswith("-USD")
        or symbol.endswith("-USDT")
        or symbol.endswith("-USDC")
    )


def _normalize_market_data_ticker(ticker: str, asset_type: str = "") -> str:
    symbol = str(ticker or "").strip().upper()
    if str(asset_type).lower() == "crypto" and symbol in CRYPTO_TICKERS:
        return f"{symbol}-USD"
    return symbol


def _sanitize_user_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "local"
    safe = USER_ID_RE.sub("-", raw).strip(".-_")
    return (safe[:64] or "local")


def _auth_dir() -> Path:
    base_cache = Path(DEFAULT_CONFIG["data_cache_dir"]).expanduser()
    return base_cache.parent / "workbench_auth"


def _auth_users_file() -> Path:
    return _auth_dir() / "users.json"


def _auth_sessions_file() -> Path:
    return _auth_dir() / "sessions.json"


def _auth_challenges_file() -> Path:
    return _auth_dir() / "challenges.json"


def _auth_audit_file() -> Path:
    return _auth_dir() / "audit.jsonl"


def _load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    tmp_file.write_text(json.dumps(_json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(path)


def _normalize_username(value: str) -> str:
    return str(value or "").strip().lower()


def _validate_username(username: str) -> str:
    normalized = _normalize_username(username)
    if not AUTH_USERNAME_RE.match(normalized):
        raise ValueError("用户名需为 3-32 位，只能包含字母、数字、下划线、点或短横线。")
    return normalized


def _validate_password(password: str) -> None:
    if len(str(password or "")) < 8:
        raise ValueError("密码至少需要 8 位。")


def _hash_password(password: str, salt_hex: str | None = None, iterations: int = 240_000) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        method, iterations_raw, salt_hex, expected = stored_hash.split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        actual = _hash_password(password, salt_hex=salt_hex, iterations=int(iterations_raw)).split("$", 3)[3]
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_auth_payload(username: str, user_id: str, role: str = "user") -> dict[str, Any]:
    return {
        "authenticated": True,
        "username": username,
        "user_id": user_id,
        "role": role or "user",
        "is_admin": role == "admin",
    }


def _append_auth_audit(event: str, actor: str = "", target: str = "", details: dict[str, Any] | None = None) -> None:
    row = {
        "ts": datetime.datetime.now().isoformat(),
        "event": event,
        "actor": actor,
        "target": target,
        "details": details or {},
    }
    with AUTH_LOCK:
        path = _auth_audit_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_json_safe(row), ensure_ascii=False) + "\n")


def _active_admin_count(users: dict[str, Any]) -> int:
    return sum(
        1
        for user in users.values()
        if isinstance(user, dict)
        and user.get("role") == "admin"
        and not bool(user.get("disabled"))
    )


def _load_auth_users_locked() -> dict[str, Any]:
    data = _load_json_file(_auth_users_file(), {"users": {}})
    data.setdefault("users", {})
    changed = False
    has_admin = any((user or {}).get("role") == "admin" for user in data["users"].values() if isinstance(user, dict))
    first_username = ""
    if data["users"]:
        first_username = sorted(
            data["users"],
            key=lambda name: str((data["users"].get(name) or {}).get("created_at") or ""),
        )[0]
    for username, user in data["users"].items():
        if not isinstance(user, dict):
            continue
        if "role" not in user:
            user["role"] = "admin" if not has_admin and username == first_username else "user"
            changed = True
        if "disabled" not in user:
            user["disabled"] = False
            changed = True
        if "last_login_at" not in user:
            user["last_login_at"] = ""
            changed = True
        if "failed_login_count" not in user:
            user["failed_login_count"] = 0
            changed = True
        if "locked_until" not in user:
            user["locked_until"] = 0
            changed = True
    if changed:
        _write_json_file(_auth_users_file(), data)
    return data


def _save_auth_users_locked(data: dict[str, Any]) -> None:
    _write_json_file(_auth_users_file(), data)


def _load_auth_sessions_locked() -> dict[str, Any]:
    data = _load_json_file(_auth_sessions_file(), {"sessions": {}})
    data.setdefault("sessions", {})
    return data


def _save_auth_sessions_locked(data: dict[str, Any]) -> None:
    _write_json_file(_auth_sessions_file(), data)


def _load_auth_challenges_locked() -> dict[str, Any]:
    data = _load_json_file(_auth_challenges_file(), {"challenges": {}})
    data.setdefault("challenges", {})
    return data


def _save_auth_challenges_locked(data: dict[str, Any]) -> None:
    _write_json_file(_auth_challenges_file(), data)


def _create_auth_challenge() -> dict[str, Any]:
    challenge_id = secrets.token_urlsafe(18)
    target = secrets.randbelow(51) + 25
    tolerance = 4
    expires_at = time.time() + AUTH_CHALLENGE_TTL_SECONDS
    with AUTH_LOCK:
        data = _load_auth_challenges_locked()
        now = time.time()
        data["challenges"] = {
            key: value
            for key, value in data["challenges"].items()
            if float(value.get("expires_at") or 0) > now
        }
        data["challenges"][challenge_id] = {
            "type": "slider",
            "target": target,
            "tolerance": tolerance,
            "expires_at": expires_at,
        }
        _save_auth_challenges_locked(data)
    return {
        "challenge_id": challenge_id,
        "type": "slider",
        "prompt": "拖动滑块到目标区域",
        "target_percent": target,
        "tolerance": tolerance,
        "expires_in": AUTH_CHALLENGE_TTL_SECONDS,
    }


def _verify_auth_challenge(challenge_id: str, answer: Any) -> bool:
    with AUTH_LOCK:
        data = _load_auth_challenges_locked()
        challenge = data["challenges"].pop(str(challenge_id or ""), None)
        now = time.time()
        data["challenges"] = {
            key: value
            for key, value in data["challenges"].items()
            if float(value.get("expires_at") or 0) > now
        }
        _save_auth_challenges_locked(data)
    if not isinstance(challenge, dict):
        return False
    if float(challenge.get("expires_at") or 0) < time.time():
        return False
    if challenge.get("type") == "slider":
        try:
            if isinstance(answer, str):
                answer_payload = json.loads(answer)
            else:
                answer_payload = answer if isinstance(answer, dict) else {}
            value = float(answer_payload.get("value"))
            elapsed_ms = int(answer_payload.get("elapsed_ms") or 0)
            moves = int(answer_payload.get("moves") or 0)
            target = float(challenge.get("target"))
            tolerance = float(challenge.get("tolerance") or 4)
        except Exception:
            return False
        return (
            abs(value - target) <= tolerance
            and 350 <= elapsed_ms <= 30_000
            and moves >= 4
        )
    return hmac.compare_digest(str(challenge.get("answer_hash") or ""), _token_hash(str(answer or "").strip()))


def _register_auth_user(username: str, password: str) -> dict[str, Any]:
    normalized = _validate_username(username)
    _validate_password(password)
    with AUTH_LOCK:
        data = _load_auth_users_locked()
        if normalized in data["users"]:
            raise ValueError("该用户名已存在。")
        role = "admin" if not data["users"] else "user"
        user = {
            "username": normalized,
            "user_id": _sanitize_user_id(normalized),
            "role": role,
            "disabled": False,
            "password_hash": _hash_password(password),
            "created_at": datetime.datetime.now().isoformat(),
            "last_login_at": "",
            "failed_login_count": 0,
            "locked_until": 0,
        }
        data["users"][normalized] = user
        _save_auth_users_locked(data)
        _append_auth_audit("user_registered", actor=normalized, target=normalized, details={"role": role})
        return user


def _authenticate_user(username: str, password: str) -> tuple[dict[str, Any] | None, str]:
    normalized = _normalize_username(username)
    with AUTH_LOCK:
        data = _load_auth_users_locked()
        user = data["users"].get(normalized)
        if not isinstance(user, dict):
            _append_auth_audit("login_failed", actor=normalized, target=normalized, details={"reason": "unknown_user"})
            return None, "用户名或密码不正确。"
        if bool(user.get("disabled")):
            _append_auth_audit("login_failed", actor=normalized, target=normalized, details={"reason": "disabled"})
            return None, "账号已被禁用，请联系管理员。"
        locked_until = float(user.get("locked_until") or 0)
        if locked_until > time.time():
            seconds = max(1, int(locked_until - time.time()))
            return None, f"登录失败次数过多，请 {seconds} 秒后再试。"
        if not _verify_password(password, str(user.get("password_hash") or "")):
            failed_count = int(user.get("failed_login_count") or 0) + 1
            user["failed_login_count"] = failed_count
            if failed_count >= AUTH_FAILED_LOGIN_LIMIT:
                user["locked_until"] = time.time() + AUTH_LOCKOUT_SECONDS
            _save_auth_users_locked(data)
            _append_auth_audit(
                "login_failed",
                actor=normalized,
                target=normalized,
                details={"reason": "bad_password", "failed_login_count": failed_count},
            )
            if failed_count >= AUTH_FAILED_LOGIN_LIMIT:
                return None, "登录失败次数过多，账号已临时锁定 5 分钟。"
            return None, "用户名或密码不正确。"
        user["last_login_at"] = datetime.datetime.now().isoformat()
        user["failed_login_count"] = 0
        user["locked_until"] = 0
        user.setdefault("role", "user")
        user.setdefault("disabled", False)
        _save_auth_users_locked(data)
        _append_auth_audit("login_success", actor=normalized, target=normalized)
        return user, ""


def _create_auth_session(user: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with AUTH_LOCK:
        data = _load_auth_sessions_locked()
        data["sessions"][_token_hash(token)] = {
            "username": user["username"],
            "user_id": user["user_id"],
            "role": user.get("role") or "user",
            "created_at": datetime.datetime.now().isoformat(),
            "expires_at": now + AUTH_SESSION_TTL_SECONDS,
        }
        _save_auth_sessions_locked(data)
    return token


def _auth_cookie(token: str) -> str:
    return (
        f"{AUTH_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; "
        f"Max-Age={AUTH_SESSION_TTL_SECONDS}"
    )


def _clear_auth_cookie() -> str:
    return f"{AUTH_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def _cookie_token(handler: SimpleHTTPRequestHandler) -> str:
    raw_cookie = handler.headers.get("Cookie", "")
    if not raw_cookie:
        return ""
    try:
        cookies = SimpleCookie(raw_cookie)
        morsel = cookies.get(AUTH_COOKIE_NAME)
        return morsel.value if morsel else ""
    except Exception:
        return ""


def _current_auth_session(handler: SimpleHTTPRequestHandler) -> dict[str, Any] | None:
    token = _cookie_token(handler)
    if not token:
        return None
    token_key = _token_hash(token)
    with AUTH_LOCK:
        data = _load_auth_sessions_locked()
        session = data["sessions"].get(token_key)
        if not isinstance(session, dict):
            return None
        if float(session.get("expires_at") or 0) < time.time():
            data["sessions"].pop(token_key, None)
            _save_auth_sessions_locked(data)
            return None
        users = _load_auth_users_locked()
        user = users["users"].get(str(session.get("username") or ""))
        if not isinstance(user, dict) or bool(user.get("disabled")):
            data["sessions"].pop(token_key, None)
            _save_auth_sessions_locked(data)
            return None
        session["role"] = user.get("role") or "user"
        return session


def _delete_auth_session(handler: SimpleHTTPRequestHandler) -> None:
    token = _cookie_token(handler)
    if not token:
        return
    with AUTH_LOCK:
        data = _load_auth_sessions_locked()
        data["sessions"].pop(_token_hash(token), None)
        _save_auth_sessions_locked(data)


def _history_summary_for_user(user_id: str) -> dict[str, Any]:
    rows = _load_persisted_history(user_id, limit=200)
    recent = rows[0] if rows else {}
    return {
        "history_count": len(rows),
        "last_run_at": recent.get("updated_at") or recent.get("created_at") or "",
        "last_ticker": recent.get("ticker") or "",
        "last_status": recent.get("status") or "",
    }


def _admin_users_payload() -> dict[str, Any]:
    with AUTH_LOCK:
        users = _load_auth_users_locked()["users"]
    items = []
    for username, user in sorted(users.items()):
        user_id = _sanitize_user_id(str(user.get("user_id") or username))
        items.append(
            {
                "username": username,
                "user_id": user_id,
                "role": user.get("role") or "user",
                "disabled": bool(user.get("disabled")),
                "created_at": user.get("created_at") or "",
                "last_login_at": user.get("last_login_at") or "",
                "failed_login_count": int(user.get("failed_login_count") or 0),
                "locked": float(user.get("locked_until") or 0) > time.time(),
                **_history_summary_for_user(user_id),
            }
        )
    return {"items": items, "count": len(items)}


def _admin_update_user(actor: str, target_username: str, updates: dict[str, Any]) -> dict[str, Any]:
    target = _validate_username(target_username)
    with AUTH_LOCK:
        data = _load_auth_users_locked()
        users = data["users"]
        user = users.get(target)
        if not isinstance(user, dict):
            raise ValueError("用户不存在。")

        new_role = str(updates.get("role") or user.get("role") or "user")
        if new_role not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user。")
        new_disabled = bool(updates.get("disabled")) if "disabled" in updates else bool(user.get("disabled"))
        is_active_admin = user.get("role") == "admin" and not bool(user.get("disabled"))
        would_remove_active_admin = is_active_admin and (new_role != "admin" or new_disabled)
        if would_remove_active_admin and _active_admin_count(users) <= 1:
            raise ValueError("不能禁用或降级最后一个启用中的管理员。")
        if target == actor and (new_role != "admin" or new_disabled):
            raise ValueError("不能禁用或降级当前登录的管理员账号。")

        user["role"] = new_role
        user["disabled"] = new_disabled
        if updates.get("unlock"):
            user["failed_login_count"] = 0
            user["locked_until"] = 0
        user["updated_at"] = datetime.datetime.now().isoformat()
        _save_auth_users_locked(data)
        _append_auth_audit(
            "admin_update_user",
            actor=actor,
            target=target,
            details={"role": new_role, "disabled": new_disabled, "unlock": bool(updates.get("unlock"))},
        )
        return user


def _admin_reset_password(actor: str, target_username: str, new_password: str) -> dict[str, Any]:
    target = _validate_username(target_username)
    _validate_password(new_password)
    with AUTH_LOCK:
        data = _load_auth_users_locked()
        user = data["users"].get(target)
        if not isinstance(user, dict):
            raise ValueError("用户不存在。")
        user["password_hash"] = _hash_password(new_password)
        user["failed_login_count"] = 0
        user["locked_until"] = 0
        user["updated_at"] = datetime.datetime.now().isoformat()
        _save_auth_users_locked(data)

        sessions = _load_auth_sessions_locked()
        sessions["sessions"] = {
            key: value
            for key, value in sessions["sessions"].items()
            if value.get("username") != target
        }
        _save_auth_sessions_locked(sessions)
        _append_auth_audit("admin_reset_password", actor=actor, target=target)
        return user


def _admin_delete_user(actor: str, target_username: str) -> None:
    target = _validate_username(target_username)
    with AUTH_LOCK:
        data = _load_auth_users_locked()
        users = data["users"]
        user = users.get(target)
        if not isinstance(user, dict):
            raise ValueError("用户不存在。")
        if target == actor:
            raise ValueError("不能删除当前登录的管理员账号。")
        is_active_admin = user.get("role") == "admin" and not bool(user.get("disabled"))
        if is_active_admin and _active_admin_count(users) <= 1:
            raise ValueError("不能删除最后一个启用中的管理员。")

        target_user_id = _sanitize_user_id(str(user.get("user_id") or target))
        active_run_ids = [
            str(run_id)
            for run_id, run in RUNS.items()
            if _sanitize_user_id(str(run.get("user_id") or "")) == target_user_id
            and run.get("status") in {"queued", "running", "cancelling"}
        ]
        if active_run_ids:
            raise ValueError("该用户还有运行中或排队中的任务，请先取消或等待结束后再删除。")

        users.pop(target, None)
        _save_auth_users_locked(data)

        sessions = _load_auth_sessions_locked()
        sessions["sessions"] = {
            key: value
            for key, value in sessions["sessions"].items()
            if value.get("username") != target
        }
        _save_auth_sessions_locked(sessions)

        for run_id, run in list(RUNS.items()):
            if _sanitize_user_id(str(run.get("user_id") or "")) == target_user_id:
                RUNS.pop(run_id, None)

        removed_paths = []
        for path in (_workbench_user_root(target_user_id), _report_root_for_user(target_user_id)):
            if path.exists():
                shutil.rmtree(path)
                removed_paths.append(str(path))

        _append_auth_audit(
            "admin_delete_user",
            actor=actor,
            target=target,
            details={"user_id": target_user_id, "removed_paths": removed_paths},
        )


def _workbench_user_root(user_id: str) -> Path:
    base_cache = Path(DEFAULT_CONFIG["data_cache_dir"]).expanduser()
    return base_cache.parent / "workbench_users" / _sanitize_user_id(user_id)


def _workbench_history_dir(user_id: str) -> Path:
    return _workbench_user_root(user_id) / "workbench_history"


def _run_snapshot_file(user_id: str, run_id: str) -> Path:
    return _workbench_history_dir(user_id) / f"{_sanitize_user_id(run_id)}.json"


def _workbench_settings_file(user_id: str) -> Path:
    return _workbench_user_root(user_id) / "workbench_settings.json"


def _load_workbench_settings(user_id: str) -> dict[str, Any]:
    path = _workbench_settings_file(user_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_workbench_settings(user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    path = _workbench_settings_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _load_workbench_settings(user_id)
    current.update(updates)
    current["updated_at"] = datetime.datetime.now().isoformat()
    tmp_file = path.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(_json_safe(current), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(path)
    return current


def _apply_user_namespace_to_config(config: dict[str, Any], user_id: str) -> dict[str, Any]:
    root = _workbench_user_root(user_id)
    config["results_dir"] = str(root / "logs")
    config["data_cache_dir"] = str(root / "cache")
    config["memory_log_path"] = str(root / "memory" / "trading_memory.md")
    config["alpha_registry_path"] = str(root / "alpha" / "alpha_registry.json")
    config["alpha_history_path"] = str(root / "alpha" / "alpha_history.json")
    return config


def _request_user_id(handler: SimpleHTTPRequestHandler, payload: dict[str, Any] | None = None) -> str:
    session = _current_auth_session(handler)
    if session:
        return _sanitize_user_id(str(session.get("user_id") or ""))
    header_value = handler.headers.get("X-TradingAgents-User", "")
    payload_value = str((payload or {}).get("user_id") or "")
    query_value = ""
    try:
        parsed = urlparse(handler.path)
        query_value = str((parse_qs(parsed.query).get("user_id") or [""])[0])
    except Exception:
        query_value = ""
    return _sanitize_user_id(header_value or payload_value or query_value)


def _report_root_for_user(user_id: str) -> Path:
    return PROJECT_ROOT / "reports" / "users" / _sanitize_user_id(user_id)


def _now_elapsed(started_at: float) -> str:
    total_seconds = max(0, int(time.time() - started_at))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump())
        except Exception:
            return str(value)
    return str(value)


def _persist_run_snapshot(run: dict[str, Any]) -> None:
    run_id = str(run.get("run_id") or "").strip()
    user_id = _sanitize_user_id(str(run.get("user_id") or "local"))
    if not run_id:
        return
    try:
        payload = _public_run_payload(run)
        payload["persisted_at"] = datetime.datetime.now().isoformat()
        history_dir = _workbench_history_dir(user_id)
        history_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = _run_snapshot_file(user_id, run_id).with_suffix(".json.tmp")
        tmp_file.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_file.replace(_run_snapshot_file(user_id, run_id))
    except Exception as error:
        print(f"[persist] failed run={run_id}: {type(error).__name__}: {error}", flush=True)


def _load_persisted_run(run_id: str, user_id: str) -> dict[str, Any] | None:
    path = _run_snapshot_file(user_id, run_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    payload.setdefault("run_id", run_id)
    payload.setdefault("user_id", _sanitize_user_id(user_id))
    if payload.get("status") in {"queued", "running", "cancelling"}:
        payload["status"] = "stale"
        payload["phase"] = "服务已重启，任务状态需重新运行"
        payload["result"] = payload.get("result") or {
            "rating": "Stale",
            "confidence": 0.0,
            "position": "N/A",
            "summary": "该任务来自服务端历史快照，原执行线程已不存在。",
        }
    _backfill_factor_runtime_from_state_log(payload)
    return payload


def _load_persisted_history(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    history_dir = _workbench_history_dir(user_id)
    if not history_dir.exists():
        return []
    rows = []
    for path in sorted(history_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("status") in {"queued", "running", "cancelling"}:
            row["status"] = "stale"
            row["phase"] = "服务已重启，任务状态需重新运行"
        _backfill_factor_runtime_from_state_log(row)
        rows.append(row)
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: str(row.get("updated_at") or row.get("persisted_at") or ""), reverse=True)
    return rows


def _delete_persisted_run(run_id: str, user_id: str, delete_artifacts: bool = False) -> dict[str, Any]:
    run = RUNS.pop(run_id, None)
    snapshot = _load_persisted_run(run_id, user_id) or {}
    path = _run_snapshot_file(user_id, run_id)
    deleted: list[str] = []
    if path.exists():
        path.unlink()
        deleted.append(str(path))
    if delete_artifacts:
        report_path = str(
            (run or {}).get("attachments", {}).get("report_path")
            or snapshot.get("attachments", {}).get("report_path")
            or ""
        ).strip()
        if report_path:
            report_root = Path(report_path).expanduser()
            allowed_root = _report_root_for_user(user_id).resolve()
            try:
                resolved = report_root.resolve()
                if resolved == allowed_root or allowed_root in resolved.parents:
                    if resolved.is_dir():
                        shutil.rmtree(resolved)
                        deleted.append(str(resolved))
                    elif resolved.exists():
                        resolved.unlink()
                        deleted.append(str(resolved))
            except Exception as error:
                return {"ok": False, "deleted": deleted, "error": f"artifact_delete_failed: {error}"}
    return {"ok": True, "deleted": deleted}


def _health_payload(user_id: str) -> dict[str, Any]:
    history_dir = _workbench_history_dir(user_id)
    report_dir = _report_root_for_user(user_id)
    settings = _load_workbench_settings(user_id)
    llm_timeout = int(settings.get("llm_timeout") or DEFAULT_CONFIG.get("timeout") or 90)
    llm_max_retries = int(
        settings.get("llm_max_retries")
        if settings.get("llm_max_retries") is not None
        else (DEFAULT_CONFIG.get("max_retries") if DEFAULT_CONFIG.get("max_retries") is not None else 2)
    )
    history_writable = True
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        probe = history_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception:
        history_writable = False
    provider_envs = {
        "openai": "OPENAI_API_KEY",
        "qwen-cn": "DASHSCOPE_CN_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }
    return {
        "ok": history_writable,
        "mode": "python-bridge-real",
        "queue": _run_queue_snapshot(),
        "history_dir": str(history_dir),
        "history_writable": history_writable,
        "report_dir": str(report_dir),
        "llm_timeout": llm_timeout,
        "llm_max_retries": llm_max_retries,
        "settings_updated_at": settings.get("updated_at", ""),
        "providers": {
            provider: {
                "api_key_env": env_name,
                "api_key_present": bool(os.environ.get(env_name)),
            }
            for provider, env_name in provider_envs.items()
        },
    }


def _persist_api_key(payload: dict[str, Any]) -> str | None:
    env_name = str(payload.get("api_key_env_name") or "").strip()
    key_value = str(payload.get("api_key_value") or "").strip()
    should_persist = bool(payload.get("ensure_api_key"))

    if not should_persist or not env_name or not key_value:
        return None
    if payload.get("user_id"):
        return "当前任务环境变量（多人模式下不写入公共 .env）"

    env_path = PROJECT_ROOT / ".env"
    env_path.touch(exist_ok=True)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []
    for line in existing_lines:
        if line.startswith(f"{env_name}="):
            new_lines.append(f"{env_name}={key_value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{env_name}={key_value}")
    env_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    os.environ[env_name] = key_value
    return str(env_path)


def _localize_structured_summary_text(text: Any, output_language: str = "") -> str:
    rendered = str(text or "")
    if str(output_language).lower() not in {"chinese", "zh", "zh-cn", "中文"}:
        return rendered

    lines = []
    for line in rendered.splitlines():
        stripped = line.strip()
        if stripped in STRUCTURED_SUMMARY_LABELS:
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}{STRUCTURED_SUMMARY_LABELS[stripped]}")
            continue

        if ":" in stripped:
            key, value = stripped.split(":", 1)
            normalized_key = key.strip()
            label = STRUCTURED_SUMMARY_LABELS.get(normalized_key)
            if label:
                indent = line[: len(line) - len(line.lstrip())]
                value_text = value.strip()
                value_text = STANCE_LABELS.get(value_text, value_text)
                lines.append(f"{indent}{label}: {value_text}")
                continue

        lines.append(line)
    return "\n".join(lines)


def _default_results_dir() -> Path:
    return Path(DEFAULT_CONFIG["results_dir"]).expanduser()


def _load_reference_text(reference_path: Path) -> str:
    suffix = reference_path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return extract_reference_text_from_html_file(reference_path)
    if suffix == ".pdf":
        return extract_reference_text_from_pdf_file(reference_path)
    return reference_path.read_text(encoding="utf-8")


def _resolve_reference_path(raw_path: str, user_id: str) -> Path:
    reference_path = Path(str(raw_path or "").strip()).expanduser()
    if not reference_path.is_absolute():
        reference_path = PROJECT_ROOT / reference_path
    reference_path = reference_path.resolve()

    allowed_roots = [
        _report_root_for_user(user_id).resolve(),
        (PROJECT_ROOT / "研报").resolve(),
    ]
    for root in allowed_roots:
        if reference_path == root or root in reference_path.parents:
            return reference_path
    raise ValueError("参考文件路径必须位于当前用户报告目录或项目研报目录。")


def _save_report_evaluation_to_disk(evaluation: Any, save_path: Path) -> Path:
    evaluation_dir = save_path / "7_evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    file_path = evaluation_dir / "report_evaluation.md"
    file_path.write_text(render_report_evaluation(evaluation), encoding="utf-8")
    return file_path


def _parse_holding_days_input(raw: str) -> list[int]:
    raw = str(raw).replace("，", ",").replace(" ", "")
    values = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        values.append(max(1, int(token)))
    return values or [5]


def _parse_initial_capital_input(raw: str) -> float:
    normalized = str(raw).replace(",", "").strip()
    if not normalized:
        return 1.0
    return max(0.01, float(normalized))


def _save_backtest_result_to_disk(
    result: BacktestResult,
    ticker: str,
    trade_date: str,
    holding_days: int,
    save_path: Path,
) -> Path:
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / f"backtest_{ticker}_{trade_date}_{holding_days}d.md"

    lines = [
        f"# Backtest Result: {ticker}",
        "",
        f"- Trade Date: {trade_date}",
        f"- Holding Days: {holding_days}",
        "",
    ]

    if not result.trades:
        lines.extend(["## Outcome", "", "No backtest trade could be resolved for this scenario."])
    else:
        trade = result.trades[0]
        metrics = result.metrics
        lines.extend(
            [
                "## Trade",
                "",
                f"- Rating: {trade.rating}",
                f"- Action: {trade.action}",
                f"- Target Position Size: {trade.target_position_size:.2%}",
                f"- Risk Gate Approved: {trade.risk_gate_approved}",
                f"- Benchmark: {trade.benchmark}",
                f"- Initial Capital: {trade.initial_capital:,.2f}",
                f"- Ending Capital: {trade.ending_capital:,.2f}",
                f"- Raw Return: {trade.raw_return:.2%}",
                f"- Executed Return: {trade.executed_return:.2%}",
                f"- Alpha Return: {trade.alpha_return:.2%}",
                f"- Executed Alpha Return: {trade.executed_alpha_return:.2%}",
                f"- Confidence: {trade.confidence:.2%}",
                "",
                "## Metrics",
                "",
                f"- Trade Count: {metrics.trade_count}",
                f"- Total Return: {metrics.total_return:.2%}",
                f"- Average Return: {metrics.average_return:.2%}",
                f"- Average Alpha: {metrics.average_alpha:.2%}",
                f"- Win Rate: {metrics.win_rate:.2%}",
                f"- Loss Rate: {metrics.loss_rate:.2%}",
                f"- Volatility: {metrics.volatility:.4f}",
                f"- Sharpe Ratio: {metrics.sharpe_ratio:.4f}",
                f"- Max Drawdown: {metrics.max_drawdown:.2%}",
            ]
        )

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def _save_backtest_summary_to_disk(
    results: list[tuple[int, BacktestResult]],
    ticker: str,
    trade_date: str,
    save_path: Path,
) -> Path:
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / f"backtest_summary_{ticker}_{trade_date}.md"
    lines = [
        f"# Backtest Summary: {ticker}",
        "",
        f"- Trade Date: {trade_date}",
        "",
        "| Holding Days | Trade Count | Rating | Action | Ending Capital | Executed Return | Executed Alpha | Win Rate | Sharpe | Max Drawdown |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for holding_days, result in results:
        if result.trades:
            trade = result.trades[0]
            metrics = result.metrics
            lines.append(
                f"| {holding_days} | {metrics.trade_count} | {trade.rating} | {trade.action} | {trade.ending_capital:,.2f} | "
                f"{trade.executed_return:.2%} | {trade.executed_alpha_return:.2%} | "
                f"{metrics.win_rate:.2%} | {metrics.sharpe_ratio:.4f} | {metrics.max_drawdown:.2%} |"
            )
        else:
            lines.append(f"| {holding_days} | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def _append_backtest_summary_to_report(report_file: Path, summary_file: Path) -> None:
    if not report_file.exists() or not summary_file.exists():
        return
    report_text = report_file.read_text(encoding="utf-8")
    summary_text = summary_file.read_text(encoding="utf-8")
    merged = report_text.rstrip() + "\n\n---\n\n## VI. Backtest Summary\n\n" + summary_text + "\n"
    report_file.write_text(merged, encoding="utf-8")


def _backtest_unresolved_reason(
    holding_days: int,
    ticker: str,
    trade_date: str,
    asset_type: str,
    benchmark: str,
) -> str:
    reason = (
        f"未解析到 {holding_days}d 回测交易：通常是分析日期 {trade_date} 距离当前日期太近，"
        f"未来 {holding_days} 天持有期行情尚未产生；也可能是数据源没有 {ticker} 在该日期后的 OHLCV。"
        f"建议把分析日期提前至少 {holding_days + 7} 天，或检查行情代码/数据源。"
    )
    if str(asset_type).lower() == "crypto":
        reason += (
            f" Crypto 默认 benchmark 为 {benchmark}；如果标的本身就是 {benchmark}，"
            "alpha 为 0 属于对自身基准比较，应重点查看 Return，或手动指定 ETH-USD/SPY 等其他 benchmark。"
        )
    return reason


def _backtest_result_payload(
    holding_days: int,
    result: BacktestResult,
    ticker: str = "",
    trade_date: str = "",
    asset_type: str = "stock",
    benchmark: str = "",
) -> dict[str, Any]:
    metrics = result.metrics.model_dump() if hasattr(result.metrics, "model_dump") else {}
    trade = result.trades[0].model_dump() if result.trades and hasattr(result.trades[0], "model_dump") else None
    return {
        "holding_days": holding_days,
        "resolved": bool(result.trades),
        "reason": "" if result.trades else _backtest_unresolved_reason(holding_days, ticker, trade_date, asset_type, benchmark),
        "trade": trade,
        "metrics": metrics,
    }


def _append_report_evaluation_to_report(report_file: Path, evaluation_file: Path) -> None:
    if not report_file.exists() or not evaluation_file.exists():
        return
    report_text = report_file.read_text(encoding="utf-8")
    evaluation_text = evaluation_file.read_text(encoding="utf-8")
    merged = report_text.rstrip() + "\n\n---\n\n## VI. Report Evaluation\n\n" + evaluation_text + "\n"
    report_file.write_text(merged, encoding="utf-8")


def _save_report_to_disk(final_state: dict[str, Any], ticker: str, save_path: Path, output_language: str = "") -> Path:
    save_path.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []

    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        report_text = _localize_structured_summary_text(final_state["market_report"], output_language)
        (analysts_dir / "market.md").write_text(report_text, encoding="utf-8")
        analyst_parts.append(("Market Analyst", report_text))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        report_text = _localize_structured_summary_text(final_state["sentiment_report"], output_language)
        (analysts_dir / "sentiment.md").write_text(report_text, encoding="utf-8")
        analyst_parts.append(("Sentiment Analyst", report_text))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        report_text = _localize_structured_summary_text(final_state["news_report"], output_language)
        (analysts_dir / "news.md").write_text(report_text, encoding="utf-8")
        analyst_parts.append(("News Analyst", report_text))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        report_text = _localize_structured_summary_text(final_state["fundamentals_report"], output_language)
        (analysts_dir / "fundamentals.md").write_text(report_text, encoding="utf-8")
        analyst_parts.append(("Fundamentals Analyst", report_text))
    if analyst_parts:
        sections.append(
            "## I. Analyst Team Reports\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        )

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(debate["bull_history"], output_language)
            (research_dir / "bull.md").write_text(report_text, encoding="utf-8")
            research_parts.append(("Bull Researcher", report_text))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(debate["bear_history"], output_language)
            (research_dir / "bear.md").write_text(report_text, encoding="utf-8")
            research_parts.append(("Bear Researcher", report_text))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(debate["judge_decision"], output_language)
            (research_dir / "manager.md").write_text(report_text, encoding="utf-8")
            research_parts.append(("Research Manager", report_text))
        if research_parts:
            sections.append(
                "## II. Research Team Decision\n\n"
                + "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            )

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        report_text = _localize_structured_summary_text(final_state["trader_investment_plan"], output_language)
        (trading_dir / "trader.md").write_text(report_text, encoding="utf-8")
        sections.append(f"## III. Trading Team Plan\n\n### Trader\n{report_text}")

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(risk["aggressive_history"], output_language)
            (risk_dir / "aggressive.md").write_text(report_text, encoding="utf-8")
            risk_parts.append(("Aggressive Analyst", report_text))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(risk["conservative_history"], output_language)
            (risk_dir / "conservative.md").write_text(report_text, encoding="utf-8")
            risk_parts.append(("Conservative Analyst", report_text))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(risk["neutral_history"], output_language)
            (risk_dir / "neutral.md").write_text(report_text, encoding="utf-8")
            risk_parts.append(("Neutral Analyst", report_text))
        if risk_parts:
            sections.append(
                "## IV. Risk Management Team Decision\n\n"
                + "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            )
        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            report_text = _localize_structured_summary_text(risk["judge_decision"], output_language)
            (portfolio_dir / "decision.md").write_text(report_text, encoding="utf-8")
            sections.append(f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{report_text}")

    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    report_file = save_path / "complete_report.md"
    report_file.write_text(header + "\n\n".join(sections), encoding="utf-8")
    return report_file


def _load_alpha_state_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_alpha_state_files(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.glob("full_states_log_*.json"))
    return [source]


def _build_alpha_registry_entry(payload: dict[str, Any], source_path: Path) -> AlphaRegistryEntry:
    alpha_result = payload.get("alpha_mining_result", {}) or {}
    selected = alpha_result.get("selected_alpha", {}) or {}
    entry = AlphaRegistryEntry(
        name=str(selected.get("name", "unknown_alpha")),
        hypothesis=str(selected.get("hypothesis", "")),
        expression=str(selected.get("expression", "")),
        signal_score=float(alpha_result.get("signal_score", 0.0)),
        confidence=float(alpha_result.get("confidence", 0.0)),
        stability=float(alpha_result.get("stability", 0.0)),
        redundancy_penalty=float(alpha_result.get("redundancy_penalty", 0.0)),
        evidence=[str(item) for item in selected.get("evidence", [])],
        source=str(source_path),
        trade_date=str(payload.get("trade_date", "")),
        realized_return=float(alpha_result.get("realized_return", 0.0)),
        realized_alpha=float(alpha_result.get("realized_alpha", 0.0)),
        evaluation_score=float(alpha_result.get("evaluation_score", 0.0)),
    )
    setattr(entry, "asset_type", str(payload.get("asset_type") or "stock"))
    return entry


def _resolve_benchmark_from_default_config(ticker: str) -> str:
    benchmark_map = DEFAULT_CONFIG.get("benchmark_map", {})
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(("-USD", "-USDT", "-USDC")):
        return str(DEFAULT_CONFIG.get("crypto_benchmark_ticker") or "BTC-USD")
    for suffix, benchmark in benchmark_map.items():
        if suffix and ticker_upper.endswith(suffix.upper()):
            return benchmark
    return benchmark_map.get("", "SPY")


def _run_alpha_mining_for_source(source: Path) -> tuple[Path, Path, dict[str, Any]]:
    state_files = _collect_alpha_state_files(source)
    if not state_files:
        raise FileNotFoundError(f"No alpha source files found in {source}")

    default_root = source if source.is_dir() else source.parent
    registry_file = default_root / "alpha_registry.json"
    history_file = default_root / "alpha_history.json"

    registry = AlphaRegistry(registry_file)
    history = AlphaMiningHistory(history_file)
    evaluator = AlphaEvaluator()
    miner = QuantaAlphaMiner()
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = copy.deepcopy(DEFAULT_CONFIG)
    backtester = graph.backtester if hasattr(graph, "backtester") else None
    if backtester is None:
        from tradingagents.backtesting.engine import BatchBacktester
        backtester = BatchBacktester(graph)

    registry.write_entries(registry.load())

    for state_file in state_files:
        payload = _load_alpha_state_file(state_file)
        alpha_result = miner.mine(payload)
        candidates = alpha_result.candidates or []
        mutations = [mutated for candidate in candidates for mutated in generate_mutation_set(candidate)]
        crossovers = generate_crossover_set(candidates)
        candidate_pool = candidates + mutations + crossovers

        for candidate in candidate_pool:
            alpha_result.candidates = [candidate]
            alpha_result.selected_alpha = candidate
            alpha_result.signal_score = candidate.signal_score
            alpha_result.confidence = candidate.confidence
            benchmark = "SPY"
            realized_return = 0.0
            realized_alpha = 0.0
            try:
                from tradingagents.decisioning.execution_policy import candidate_signal_to_execution
                action, target_position_size = candidate_signal_to_execution(
                    candidate.signal_score,
                    candidate.confidence,
                )
                source_ticker = str(payload.get("company_of_interest", ""))
                source_asset_type = str(payload.get("asset_type", "stock"))
                market_ticker = _normalize_market_data_ticker(source_ticker, source_asset_type)
                benchmark = _resolve_benchmark_from_default_config(market_ticker)
                raw_return, alpha_return, _actual_days = graph._fetch_returns(
                    market_ticker,
                    str(payload.get("trade_date", "")),
                    holding_days=5,
                    benchmark=benchmark,
                )
                if raw_return is not None and alpha_return is not None:
                    executed_return, executed_alpha_return = backtester._apply_execution_plan(
                        action,
                        target_position_size,
                        True,
                        raw_return,
                        alpha_return,
                    )
                    realized_return = executed_return
                    realized_alpha = executed_alpha_return
            except Exception:
                pass

            alpha_result.summary = (
                f"{alpha_result.summary} realized_return={realized_return:.2%}, "
                f"realized_alpha={realized_alpha:.2%}, benchmark={benchmark}."
            )
            enriched_payload = alpha_result.model_dump()
            enriched_payload["realized_return"] = realized_return
            enriched_payload["realized_alpha"] = realized_alpha
            enriched_payload["benchmark"] = benchmark
            evaluation = evaluator.evaluate(enriched_payload)
            if evaluation.passed:
                registry.upsert(
                    _build_alpha_registry_entry(
                        {
                            **payload,
                            "alpha_mining_result": {
                                **enriched_payload,
                                "evaluation_score": evaluation.score,
                            },
                        },
                        state_file,
                    )
                )
                episode = AlphaMiningEpisode(
                    source=str(state_file),
                    ticker=str(payload.get("company_of_interest", "")),
                    trade_date=str(payload.get("trade_date", "")),
                    payload={
                        "alpha_result": {
                            **enriched_payload,
                            "evaluation_score": evaluation.score,
                        },
                        "evaluation": {
                            "candidate_name": evaluation.candidate_name,
                            "passed": evaluation.passed,
                            "score": evaluation.score,
                            "notes": evaluation.notes,
                            "realized_return": evaluation.realized_return,
                            "realized_alpha": evaluation.realized_alpha,
                        },
                    },
                )
                setattr(episode, "asset_type", str(payload.get("asset_type") or "stock"))
                history.append(episode)

    registry_rows = registry.load()
    history_rows = history.load()
    registry.write_entries(registry_rows)
    summary = build_alpha_experience_summary(registry_rows, history_rows, selected_alpha={})
    return registry_file, history_file, summary


def _load_alpha_factors_for_ticker(ticker: str, user_id: str = "local") -> dict[str, Any]:
    ticker = ticker.strip().upper()
    user_config = _apply_user_namespace_to_config(copy.deepcopy(DEFAULT_CONFIG), user_id)
    results_root = Path(user_config["results_dir"]).expanduser()
    global_registry_file = Path(user_config["alpha_registry_path"]).expanduser()
    global_history_file = Path(user_config["alpha_history_path"]).expanduser()
    registry_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    files: list[str] = []

    if global_registry_file.exists():
        files.append(str(global_registry_file))
        registry_rows.extend(AlphaRegistry(global_registry_file).load())

    if global_history_file.exists():
        files.append(str(global_history_file))
        rows = AlphaMiningHistory(global_history_file).load()
        if ticker:
            rows = [row for row in rows if str(row.get("ticker", "")).upper() == ticker]
        history_rows.extend(rows)

    for registry_file in results_root.glob("**/alpha_registry.json"):
        files.append(str(registry_file))
        registry_rows.extend(AlphaRegistry(registry_file).load())

    for history_file in results_root.glob("**/alpha_history.json"):
        files.append(str(history_file))
        rows = AlphaMiningHistory(history_file).load()
        if ticker:
            rows = [row for row in rows if str(row.get("ticker", "")).upper() == ticker]
        history_rows.extend(rows)

    if ticker:
        registry_rows = [
            row for row in registry_rows
            if ticker in str(row.get("source", "")).upper()
            or ticker in str(row.get("name", "")).upper()
            or ticker in str(row.get("hypothesis", "")).upper()
        ]

    registry_rows = sorted(
        registry_rows,
        key=lambda row: float(row.get("evaluation_score", row.get("confidence", 0.0)) or 0.0),
        reverse=True,
    )
    history_rows = sorted(history_rows, key=lambda row: str(row.get("created_at_utc", "")), reverse=True)

    return {
        "ticker": ticker,
        "registry": registry_rows[:50],
        "history": history_rows[:50],
        "files": sorted(set(files)),
        "summary": {
            "registry_count": len(registry_rows),
            "history_count": len(history_rows),
        },
    }


def _build_run_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    user_id = _sanitize_user_id(str(payload.get("user_id") or "local"))
    _apply_user_namespace_to_config(config, user_id)
    research_depth = int(payload.get("research_depth") or 3)
    config["max_debate_rounds"] = research_depth
    config["max_risk_discuss_rounds"] = int(payload.get("max_risk_rounds") or research_depth)
    config["quick_think_llm"] = str(payload.get("quick_think_llm") or config["quick_think_llm"])
    config["deep_think_llm"] = str(payload.get("deep_think_llm") or config["deep_think_llm"])
    config["analysis_think_llm"] = str(payload.get("analysis_think_llm") or "").strip() or None
    config["debate_think_llm"] = str(payload.get("debate_think_llm") or "").strip() or None
    config["decision_think_llm"] = str(payload.get("decision_think_llm") or "").strip() or None
    config["backend_url"] = payload.get("backend_url") or None
    config["llm_provider"] = str(payload.get("llm_provider") or config["llm_provider"]).lower()
    config["google_thinking_level"] = payload.get("google_thinking_level")
    config["openai_reasoning_effort"] = payload.get("openai_reasoning_effort")
    config["anthropic_effort"] = payload.get("anthropic_effort")
    config["timeout"] = int(payload.get("llm_timeout") or config.get("timeout") or 90)
    config["max_retries"] = int(payload.get("llm_max_retries") or config.get("max_retries") or 2)
    config["output_language"] = str(payload.get("output_language") or config["output_language"])
    config["analysis_lookback_days"] = int(payload.get("analysis_lookback_days") or config["analysis_lookback_days"])
    config["checkpoint_enabled"] = bool(payload.get("checkpoint_enabled"))
    config["parallel_analysts"] = bool(payload.get("parallel_analysts"))
    config["analyst_concurrency_limit"] = (
        4 if config["parallel_analysts"] else 1
    )
    if payload.get("benchmark_ticker"):
        config["benchmark_ticker"] = str(payload["benchmark_ticker"]).strip()
    if bool(payload.get("ensure_api_key")):
        api_key = str(payload.get("api_key_value") or "").strip()
        if api_key:
            config["api_key"] = api_key
    return config


def _checkpoint_data_dir(payload: dict[str, Any] | None = None) -> str:
    return str(_build_run_config(payload or {}).get("data_cache_dir", DEFAULT_CONFIG["data_cache_dir"]))


def _resolve_api_key_for_provider(provider: str, payload: dict[str, Any]) -> str | None:
    explicit = str(payload.get("api_key_value") or "").strip()
    if explicit:
        return explicit

    env_name = str(payload.get("api_key_env_name") or "").strip()
    if env_name:
        return os.environ.get(env_name)

    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "xai": "XAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "qwen-cn": "DASHSCOPE_CN_API_KEY",
        "glm": "ZHIPU_API_KEY",
        "glm-cn": "ZHIPU_CN_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "minimax-cn": "MINIMAX_CN_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }
    return os.environ.get(provider_env_map.get(provider, ""))


def _discover_remote_models(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    provider = str(payload.get("provider") or "").strip().lower()
    base_url = str(payload.get("backend_url") or "").strip()
    api_key = _resolve_api_key_for_provider(provider, payload)

    if not base_url:
        raise ValueError("backend_url is required")

    if provider not in OPENAI_COMPATIBLE_DISCOVERY_PROVIDERS:
        raise ValueError(f"provider '{provider}' does not support remote model discovery yet")

    request = Request(base_url.rstrip("/") + "/models")
    if api_key and provider != "ollama":
        request.add_header("Authorization", f"Bearer {api_key}")
    request.add_header("Content-Type", "application/json")

    with urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        data = json.loads(body or "{}")

    models = data.get("data", [])
    ids: list[str] = []
    for item in models:
        model_id = str(item.get("id") or "").strip()
        if model_id:
            ids.append(model_id)
    ids = sorted(set(ids))

    quick = [{"label": model_id, "value": model_id} for model_id in ids]
    deep = [{"label": model_id, "value": model_id} for model_id in ids]
    return {"quick": quick, "deep": deep}


def _append_log(run: dict[str, Any], message: str) -> None:
    run["logs"].append(message)
    run["elapsed"] = _now_elapsed(run["started_at"])
    _append_event(run, "log", str(message))
    _persist_run_snapshot(run)


def _append_event(run: dict[str, Any], kind: str, message: str, data: dict[str, Any] | None = None) -> None:
    run.setdefault("events", []).append(
        {
            "ts": datetime.datetime.now().isoformat(),
            "kind": kind,
            "message": message,
            "phase": run.get("phase", ""),
            "progress": run.get("progress", 0),
            "data": data or {},
        }
    )
    if len(run["events"]) > 1000:
        run["events"] = run["events"][-1000:]


def _update_phase(run: dict[str, Any], phase: str, progress: int, message: str | None = None) -> None:
    if run.get("status") == "cancelled":
        return
    run["phase"] = phase
    run["progress"] = progress
    run["elapsed"] = _now_elapsed(run["started_at"])
    if message:
        run["logs"].append(message)
    _append_event(run, "phase", message or phase, {"phase": phase, "progress": progress})
    _persist_run_snapshot(run)


def _run_cancel_requested(run: dict[str, Any]) -> bool:
    return bool(run.get("cancel_requested")) or run.get("status") == "cancelled"


def _release_run_slot(run: dict[str, Any], reason: str = "released") -> bool:
    if not run.get("slot_acquired"):
        return False
    run["slot_acquired"] = False
    _append_event(run, "queue", reason, {"active_runs": _run_queue_snapshot(skip_heal=True)["active_runs"]})
    _persist_run_snapshot(run)
    RUN_SLOT.release()
    return True


def _mark_run_cancelled(run: dict[str, Any], message: str | None = None) -> None:
    run["cancel_requested"] = True
    run["status"] = "cancelled"
    run["phase"] = "已取消"
    run["progress"] = max(int(run.get("progress") or 0), 100)
    run["elapsed"] = _now_elapsed(run["started_at"])
    run["updated_at"] = datetime.datetime.now().isoformat()
    run["resume_hint"] = (
        "任务已取消，如 checkpoint 仍存在，可重新运行尝试恢复"
        if run.get("checkpoint_enabled")
        else "任务已取消"
    )
    if message:
        run["logs"].append(message)
    if not run.get("result"):
        run["result"] = {
            "rating": "Cancelled",
            "confidence": 0.0,
            "position": "N/A",
            "summary": "任务已取消。",
        }
    run["metrics"] = _build_metrics_snapshot(run)
    _append_event(run, "cancel", message or "任务已取消")
    _persist_run_snapshot(run)


def _request_run_cancellation(run: dict[str, Any], message: str | None = None) -> None:
    run["cancel_requested"] = True
    run["updated_at"] = datetime.datetime.now().isoformat()
    if run.get("slot_acquired") or run.get("status") == "running":
        run["status"] = "cancelling"
        run["phase"] = "取消中，等待当前调用返回并释放执行槽"
        run["resume_hint"] = "已请求取消；当前 LLM/数据调用返回后会释放执行槽"
        if message:
            run.setdefault("logs", []).append(message)
        run["metrics"] = _build_metrics_snapshot(run)
        _append_event(run, "cancel_requested", message or "已请求取消，等待执行槽释放")
        _persist_run_snapshot(run)
        return

    _mark_run_cancelled(run, message or "[cancel] 任务已取消，未占用执行槽")


def _mark_active_runs_for_workbench_restart(message: str) -> list[dict[str, Any]]:
    affected: list[dict[str, Any]] = []
    for run in RUNS.values():
        if run.get("status") not in {"queued", "running", "cancelling"}:
            continue
        run["slot_acquired"] = False
        _mark_run_cancelled(run, message)
        run["phase"] = "Workbench 重启中"
        run["resume_hint"] = "Workbench 已强制重启；阻塞中的 LLM/数据调用已被终止"
        run["metrics"] = _build_metrics_snapshot(run)
        _persist_run_snapshot(run)
        affected.append(run)
    return affected


def _schedule_workbench_restart(delay_seconds: float = 0.35) -> None:
    def _exit_process() -> None:
        print("[restart] exiting workbench process for Docker restart", flush=True)
        os._exit(3)

    timer = threading.Timer(delay_seconds, _exit_process)
    timer.daemon = True
    timer.start()


def _heal_finished_slots() -> None:
    for run in RUNS.values():
        if not run.get("slot_acquired"):
            continue
        if run.get("status") not in PERSISTED_TERMINAL_STATUSES:
            continue
        worker = run.get("worker_thread")
        if worker is not None and hasattr(worker, "is_alive") and worker.is_alive():
            continue
        _release_run_slot(run, "已自动修复已结束任务残留的执行槽")


def _active_runs_for_user(user_id: str) -> int:
    safe_user_id = _sanitize_user_id(user_id)
    return sum(
        1
        for run in RUNS.values()
        if run.get("slot_acquired")
        and run.get("status") in {"running", "cancelling"}
        and _sanitize_user_id(str(run.get("user_id") or "")) == safe_user_id
    )


def _run_queue_snapshot(skip_heal: bool = False) -> dict[str, int]:
    if not skip_heal:
        _heal_finished_slots()
    active = sum(1 for run in RUNS.values() if run.get("slot_acquired"))
    queued = sum(1 for run in RUNS.values() if run.get("status") == "queued")
    cancelling = sum(1 for run in RUNS.values() if run.get("status") == "cancelling")
    return {
        "run_concurrency": RUN_CONCURRENCY,
        "user_run_concurrency": RUN_USER_CONCURRENCY,
        "active_runs": active,
        "queued_runs": queued,
        "cancelling_runs": cancelling,
        "available_slots": max(0, RUN_CONCURRENCY - active),
    }


def _public_run_payload(run: dict[str, Any]) -> dict[str, Any]:
    """Return only JSON-safe fields the frontend actually needs."""
    _backfill_factor_runtime_from_state_log(run)
    return {
        "run_id": run.get("run_id"),
        "user_id": run.get("user_id", "local"),
        "status": run.get("status"),
        "phase": run.get("phase"),
        "progress": run.get("progress"),
        "elapsed": run.get("elapsed"),
        "payload": run.get("payload"),
        "logs": run.get("logs", []),
        "result": run.get("result"),
        "attachments": run.get("attachments", {}),
        "report_preview": run.get("report_preview", ""),
        "agent_status": run.get("agent_status", {}),
        "agent_outputs": run.get("agent_outputs", {}),
        "events": run.get("events", []),
        "decision": run.get("decision"),
        "error_message": run.get("error_message", ""),
        "metrics": run.get("metrics", {}),
        "runtime_stall": run.get("runtime_stall", None),
        "report_sections": run.get("report_sections", {}),
        "report_file": run.get("report_file", ""),
        "updated_at": run.get("updated_at", ""),
        "checkpoint_available": run.get("checkpoint_available", False),
        "checkpoint_enabled": run.get("checkpoint_enabled", False),
        "resume_hint": run.get("resume_hint", ""),
        "cancel_requested": run.get("cancel_requested", False),
        "analyst_execution_mode": run.get("analyst_execution_mode", "serial"),
        "queue": _run_queue_snapshot(),
    }


def _result_summary_from_state(final_state: dict[str, Any], decision: str) -> dict[str, Any]:
    debate_state = final_state.get("investment_debate_state", {}) or {}
    confidence = float(debate_state.get("signal_confidence", 0.0) or 0.0)
    execution_plan = final_state.get("execution_plan", {}) or {}
    execution_action = str(execution_plan.get("action") or "").strip().lower()
    target_position = execution_plan.get("target_position_size")
    if execution_action == "hold":
        target_position = 0.0
    if isinstance(target_position, (int, float)):
        position_text = f"{target_position:.0%}"
    else:
        position_text = "N/A"

    risk_state = final_state.get("risk_debate_state", {}) or {}
    raw_summary = str(risk_state.get("judge_decision") or final_state.get("final_trade_decision") or "").strip()
    details: dict[str, Any] = {}
    if raw_summary:
        try:
            parsed_decision = parse_pm_decision(raw_summary)
            details = {
                "rating": parsed_decision.rating.value,
                "executive_summary": parsed_decision.executive_summary,
                "investment_thesis": parsed_decision.investment_thesis,
                "price_target": parsed_decision.price_target,
                "time_horizon": parsed_decision.time_horizon,
                "target_position_size": parsed_decision.target_position_size,
                "risk_gate_status": parsed_decision.risk_gate_status,
                "raw_decision": raw_summary,
            }
        except Exception:
            details = {"raw_decision": raw_summary}
    if (str(details.get("rating") or decision).strip().lower() == "hold" or execution_action == "hold") and isinstance(target_position, (int, float)):
        details["target_position_size"] = target_position

    summary = str(details.get("executive_summary") or raw_summary or "").strip()
    data_diagnostic = _build_data_availability_diagnostic(final_state)
    if data_diagnostic:
        summary = f"{summary}\n\n数据诊断: {data_diagnostic}" if summary else f"数据诊断: {data_diagnostic}"

    return {
        "rating": details.get("rating") or decision,
        "confidence": confidence,
        "position": position_text,
        "summary": summary or "分析已完成，请查看完整报告。",
        "decision_details": details,
    }


def _build_data_availability_diagnostic(final_state: dict[str, Any]) -> str:
    fundamentals_report = str(final_state.get("fundamentals_report") or "")
    lowered = fundamentals_report.lower()
    if not fundamentals_report:
        return ""
    unavailable_markers = (
        "data unavailable",
        "no available vendor",
        "no balance sheet data found",
        "no cash flow data found",
        "no income statement data found",
    )
    if not any(marker in lowered for marker in unavailable_markers):
        return ""

    ticker = str(final_state.get("company_of_interest") or "该资产")
    return (
        f"{ticker} 的部分公司财报数据源不可用或不适用于该资产。"
        "结论应降低对资产负债表、现金流和利润表的依赖，优先参考价格趋势、成交/链上或新闻情绪、宏观环境和风险管理信号；"
        "若分析对象实际是上市公司股票，可补充可用的财报 vendor/API key 后重跑。"
    )


def _build_asset_type_diagnostic(ticker: str, asset_type: str) -> str:
    if str(asset_type).lower() != "crypto":
        return ""
    market_ticker = _normalize_market_data_ticker(ticker, asset_type)
    benchmark = _resolve_benchmark_from_default_config(market_ticker)
    return (
        f"{ticker} 被识别为 crypto 资产，已禁用 Fundamentals Analyst，因为公司资产负债表、现金流和利润表不适用于该资产。"
        f"系统会使用 {market_ticker} 作为行情代码，并默认用 {benchmark} 作为 crypto 回测/alpha 基准。"
        "处理建议：结论应优先参考价格趋势、成交量/流动性、波动率、回撤、新闻情绪、宏观流动性、风险管理和仓位控制信号；"
        "若该标的是上市公司股票，请把资产类型改为 stock 后重跑。"
    )


def _extract_agent_outputs(final_state: dict[str, Any], output_language: str = "") -> dict[str, str]:
    outputs: dict[str, str] = {}
    if final_state.get("market_report"):
        outputs["Market Analyst"] = _localize_structured_summary_text(final_state["market_report"], output_language)
    if final_state.get("sentiment_report"):
        outputs["Sentiment Analyst"] = _localize_structured_summary_text(final_state["sentiment_report"], output_language)
    if final_state.get("news_report"):
        outputs["News Analyst"] = _localize_structured_summary_text(final_state["news_report"], output_language)
    if final_state.get("fundamentals_report"):
        outputs["Fundamentals Analyst"] = _localize_structured_summary_text(final_state["fundamentals_report"], output_language)

    debate = final_state.get("investment_debate_state", {}) or {}
    if debate.get("bull_history"):
        outputs["Bull Researcher"] = _localize_structured_summary_text(debate["bull_history"], output_language)
    if debate.get("bear_history"):
        outputs["Bear Researcher"] = _localize_structured_summary_text(debate["bear_history"], output_language)
    if debate.get("judge_decision"):
        outputs["Research Manager"] = _localize_structured_summary_text(debate["judge_decision"], output_language)

    if final_state.get("factor_score") or final_state.get("alpha_mining_result"):
        factor_detail = _build_factor_runtime_detail(final_state)
        outputs["Factor Manager"] = _format_factor_manager_output(factor_detail)

    if final_state.get("trader_investment_plan"):
        outputs["Trader"] = _localize_structured_summary_text(final_state["trader_investment_plan"], output_language)

    risk = final_state.get("risk_debate_state", {}) or {}
    if risk.get("aggressive_history"):
        outputs["Aggressive Analyst"] = _localize_structured_summary_text(risk["aggressive_history"], output_language)
    if risk.get("neutral_history"):
        outputs["Neutral Analyst"] = _localize_structured_summary_text(risk["neutral_history"], output_language)
    if risk.get("conservative_history"):
        outputs["Conservative Analyst"] = _localize_structured_summary_text(risk["conservative_history"], output_language)
    if risk.get("judge_decision"):
        outputs["Portfolio Manager"] = _localize_structured_summary_text(risk["judge_decision"], output_language)

    return outputs


def _extract_report_sections(final_state: dict[str, Any], output_language: str = "") -> dict[str, str]:
    sections: dict[str, str] = {}
    if final_state.get("market_report"):
        sections["Market Analysis"] = _localize_structured_summary_text(final_state["market_report"], output_language)
    if final_state.get("sentiment_report"):
        sections["Sentiment Analysis"] = _localize_structured_summary_text(final_state["sentiment_report"], output_language)
    if final_state.get("news_report"):
        sections["News Analysis"] = _localize_structured_summary_text(final_state["news_report"], output_language)
    if final_state.get("fundamentals_report"):
        sections["Fundamentals Analysis"] = _localize_structured_summary_text(final_state["fundamentals_report"], output_language)
    if final_state.get("trader_investment_plan"):
        sections["Trading Plan"] = _localize_structured_summary_text(final_state["trader_investment_plan"], output_language)

    debate = final_state.get("investment_debate_state", {}) or {}
    if debate.get("judge_decision"):
        sections["Research Decision"] = _localize_structured_summary_text(debate["judge_decision"], output_language)

    risk = final_state.get("risk_debate_state", {}) or {}
    if risk.get("judge_decision"):
        sections["Portfolio Decision"] = _localize_structured_summary_text(risk["judge_decision"], output_language)
    return sections


def _merge_agent_outputs_from_chunk(run: dict[str, Any], chunk: dict[str, Any]) -> None:
    outputs = run.setdefault("agent_outputs", {})
    output_language = str(run.get("payload", {}).get("output_language") or "")

    if chunk.get("market_report"):
        outputs["Market Analyst"] = _localize_structured_summary_text(chunk["market_report"], output_language)
    if chunk.get("sentiment_report"):
        outputs["Sentiment Analyst"] = _localize_structured_summary_text(chunk["sentiment_report"], output_language)
    if chunk.get("news_report"):
        outputs["News Analyst"] = _localize_structured_summary_text(chunk["news_report"], output_language)
    if chunk.get("fundamentals_report"):
        outputs["Fundamentals Analyst"] = _localize_structured_summary_text(chunk["fundamentals_report"], output_language)

    debate = chunk.get("investment_debate_state") or {}
    if debate.get("bull_history"):
        outputs["Bull Researcher"] = _localize_structured_summary_text(debate["bull_history"], output_language)
    if debate.get("bear_history"):
        outputs["Bear Researcher"] = _localize_structured_summary_text(debate["bear_history"], output_language)
    if debate.get("judge_decision"):
        outputs["Research Manager"] = _localize_structured_summary_text(debate["judge_decision"], output_language)

    factor_score = chunk.get("factor_score") if isinstance(chunk.get("factor_score"), dict) else {}
    alpha_result = chunk.get("alpha_mining_result") if isinstance(chunk.get("alpha_mining_result"), dict) else {}
    if _has_factor_runtime_result(factor_score, alpha_result):
        factor_detail = _build_factor_runtime_detail(
            {
                "factor_score": factor_score,
                "alpha_mining_result": alpha_result,
                "alpha_experience_summary": chunk.get("alpha_experience_summary", {}),
            }
        )
        outputs["Factor Manager"] = _format_factor_manager_output(factor_detail)

    if chunk.get("trader_investment_plan"):
        outputs["Trader"] = _localize_structured_summary_text(chunk["trader_investment_plan"], output_language)

    risk = chunk.get("risk_debate_state") or {}
    if risk.get("aggressive_history"):
        outputs["Aggressive Analyst"] = _localize_structured_summary_text(risk["aggressive_history"], output_language)
    if risk.get("neutral_history"):
        outputs["Neutral Analyst"] = _localize_structured_summary_text(risk["neutral_history"], output_language)
    if risk.get("conservative_history"):
        outputs["Conservative Analyst"] = _localize_structured_summary_text(risk["conservative_history"], output_language)
    if risk.get("judge_decision"):
        outputs["Portfolio Manager"] = _localize_structured_summary_text(risk["judge_decision"], output_language)


def _build_metrics_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    agent_status = run.get("agent_status", {})
    completed = sum(1 for status in agent_status.values() if status == "completed")
    in_progress = sum(1 for status in agent_status.values() if status == "in_progress")
    return {
        "log_count": len(run.get("logs", [])),
        "completed_agents": completed,
        "in_progress_agents": in_progress,
        "report_section_count": len(run.get("report_sections", {})),
        "agent_timings": run.get("agent_timings", {}),
        "runtime": run.get("runtime_metrics", {}),
    }


def _build_factor_runtime_detail(final_state: dict[str, Any]) -> dict[str, Any]:
    factor_score = final_state.get("factor_score", {}) or {}
    alpha_result = final_state.get("alpha_mining_result", {}) or {}
    selected_alpha = alpha_result.get("selected_alpha", {}) if isinstance(alpha_result, dict) else {}
    return {
        "factor_score": factor_score,
        "alpha_mining_result": alpha_result,
        "alpha_experience_summary": final_state.get("alpha_experience_summary", {}) or {},
        "selected_alpha": selected_alpha or {},
        "signal_score": alpha_result.get("signal_score", 0.0) if isinstance(alpha_result, dict) else 0.0,
        "confidence": alpha_result.get("confidence", 0.0) if isinstance(alpha_result, dict) else 0.0,
        "composite_score": factor_score.get("composite_score", 0.0) if isinstance(factor_score, dict) else 0.0,
        "summary": factor_score.get("summary", "") if isinstance(factor_score, dict) else "",
    }


def _has_factor_runtime_result(factor_score: dict[str, Any], alpha_result: dict[str, Any]) -> bool:
    return bool(
        factor_score.get("composite_score") is not None
        or alpha_result.get("selected_alpha")
        or alpha_result.get("signal_score") is not None
    )


def _format_factor_manager_output(factor_detail: dict[str, Any]) -> str:
    selected_alpha = factor_detail.get("selected_alpha") or {}
    return (
        f"本次决策前因子评分 composite={float(factor_detail.get('composite_score') or 0.0):.4f}，"
        f"alpha signal={float(factor_detail.get('signal_score') or 0.0):.4f}，"
        f"confidence={float(factor_detail.get('confidence') or 0.0):.2%}。\n"
        f"选中因子: {selected_alpha.get('name') or 'N/A'}\n"
        f"{factor_detail.get('summary') or ''}"
    )


def _backfill_factor_runtime_from_state_log(run: dict[str, Any]) -> None:
    attachments = run.setdefault("attachments", {})
    existing_detail = attachments.get("factor_runtime_detail")
    if isinstance(existing_detail, dict) and existing_detail:
        run.setdefault("agent_outputs", {})["Factor Manager"] = _format_factor_manager_output(existing_detail)
        run.setdefault("agent_status", {})["Factor Manager"] = "completed"
        return
    final_state = run.get("final_state") if isinstance(run.get("final_state"), dict) else {}
    if final_state and (final_state.get("factor_score") or final_state.get("alpha_mining_result")):
        factor_detail = _build_factor_runtime_detail(final_state)
        attachments["factor_runtime_detail"] = factor_detail
        run.setdefault("agent_outputs", {})["Factor Manager"] = _format_factor_manager_output(factor_detail)
        run.setdefault("agent_status", {})["Factor Manager"] = "completed"
        return
    if run.get("status") not in PERSISTED_TERMINAL_STATUSES:
        return
    payload = run.get("payload") or {}
    user_id = _sanitize_user_id(str(run.get("user_id") or payload.get("user_id") or "local"))
    ticker = str(payload.get("ticker") or run.get("ticker") or "").strip().upper()
    analysis_date = str(payload.get("analysis_date") or "").strip()
    if not ticker or not analysis_date:
        return
    try:
        config = _apply_user_namespace_to_config(copy.deepcopy(DEFAULT_CONFIG), user_id)
        state_filename = f"full_states_log_{analysis_date}.json"
        state_candidates = [
            Path(config["results_dir"]) / ticker / "TradingAgentsStrategy_logs" / state_filename,
            Path.cwd() / ".tradingagents" / "workbench_users" / user_id / "logs" / ticker / "TradingAgentsStrategy_logs" / state_filename,
            Path.cwd() / ".tradingagents" / "logs" / ticker / "TradingAgentsStrategy_logs" / state_filename,
        ]
        state_file = next((candidate for candidate in state_candidates if candidate.exists()), None)
        if state_file is None:
            return
        final_state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return
    if not final_state.get("factor_score") and not final_state.get("alpha_mining_result"):
        return
    factor_detail = _build_factor_runtime_detail(final_state)
    attachments["factor_runtime_detail"] = factor_detail
    run.setdefault("agent_outputs", {})["Factor Manager"] = _format_factor_manager_output(factor_detail)
    run.setdefault("agent_status", {})["Factor Manager"] = "completed"


def _refresh_runtime_metrics(
    run: dict[str, Any],
    metrics_handler: RunMetricsCallbackHandler | None,
) -> None:
    if metrics_handler is not None:
        run["runtime_metrics"] = metrics_handler.get_metrics()
    run["metrics"] = _build_metrics_snapshot(run)


def _refresh_live_run_status(run: dict[str, Any], *, persist: bool = False) -> None:
    """Refresh metrics for a live run even while graph.stream is blocked."""
    handler = run.get("metrics_handler")
    if isinstance(handler, RunMetricsCallbackHandler):
        _refresh_runtime_metrics(run, handler)
    else:
        run["metrics"] = _build_metrics_snapshot(run)
    if run.get("started_at"):
        run["elapsed"] = _now_elapsed(run["started_at"])

    runtime = run.get("runtime_metrics", {}) if isinstance(run.get("runtime_metrics"), dict) else {}
    active_calls = runtime.get("active_llm_calls") if isinstance(runtime, dict) else []
    if not isinstance(active_calls, list) or not active_calls:
        run.pop("runtime_stall", None)
        if persist:
            _persist_run_snapshot(run)
        return

    timeout_seconds = int(run.get("payload", {}).get("llm_timeout") or DEFAULT_CONFIG.get("timeout") or 90)
    longest_call = max(
        active_calls,
        key=lambda item: float(item.get("elapsed_seconds") or 0.0) if isinstance(item, dict) else 0.0,
    )
    elapsed_seconds = float(longest_call.get("elapsed_seconds") or 0.0)
    if elapsed_seconds <= timeout_seconds + 15:
        if persist:
            _persist_run_snapshot(run)
        return

    sequence = longest_call.get("sequence")
    stall_key = f"llm-{sequence}"
    if run.get("runtime_stall", {}).get("key") == stall_key:
        if persist:
            _persist_run_snapshot(run)
        return

    run["runtime_stall"] = {
        "key": stall_key,
        "model": longest_call.get("model", "unknown"),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "timeout_seconds": timeout_seconds,
    }
    run["resume_hint"] = (
        f"当前 LLM 调用已运行 {int(elapsed_seconds)} 秒，超过配置超时 {timeout_seconds} 秒；"
        "如果长时间不返回，可使用强制重启回收执行槽。"
    )
    _append_event(
        run,
        "llm_stall",
        (
            f"LLM 调用疑似卡住 model={longest_call.get('model', 'unknown')} "
            f"elapsed={int(elapsed_seconds)}s timeout={timeout_seconds}s"
        ),
        dict(run["runtime_stall"]),
    )
    if persist:
        _persist_run_snapshot(run)


ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

TEAM_ORDER = [
    ("Analyst Team", ["Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst"]),
    ("Research Team", ["Bull Researcher", "Bear Researcher", "Research Manager", "Factor Manager"]),
    ("Trading Team", ["Trader"]),
    ("Risk Management", ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"]),
    ("Portfolio Management", ["Portfolio Manager"]),
]


def _initial_agent_status(selected_analysts: list[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for analyst_key in selected_analysts or ["market", "social", "news", "fundamentals"]:
        agent_name = ANALYST_AGENT_NAMES.get(analyst_key)
        if agent_name:
            statuses[agent_name] = "pending"
    for _team, agents in TEAM_ORDER[1:]:
        for agent in agents:
            statuses[agent] = "pending"
    return statuses


def _set_agent_status(run: dict[str, Any], agent: str, status: str) -> None:
    statuses = run.setdefault("agent_status", {})
    previous = statuses.get(agent)
    statuses[agent] = status
    if previous == status:
        return

    now = time.time()
    timings = run.setdefault("agent_timings", {})
    timing = timings.setdefault(
        agent,
        {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
        },
    )
    timing["status"] = status
    if status == "in_progress" and timing.get("started_at") is None:
        timing["started_at"] = now
    if status == "completed":
        if timing.get("started_at") is None:
            timing["started_at"] = now
        timing["completed_at"] = now
        timing["duration_seconds"] = round(
            max(0.0, now - float(timing["started_at"])),
            3,
        )


def _extract_content_string(content: Any) -> str | None:
    import ast

    def is_empty(value: Any) -> bool:
        if value is None or value == "":
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            try:
                return not bool(ast.literal_eval(stripped))
            except (ValueError, SyntaxError):
                return False
        return not bool(value)

    if is_empty(content):
        return None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    text_parts.append(text)
            elif isinstance(item, str) and item.strip():
                text_parts.append(item.strip())
        result = " ".join(text_parts)
        return result if result else None
    return str(content).strip()


def _classify_message_type(message: Any) -> tuple[str, str | None]:
    try:
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    except Exception:
        return ("System", _extract_content_string(getattr(message, "content", None)))

    content = _extract_content_string(getattr(message, "content", None))
    if isinstance(message, HumanMessage):
        return ("User", content)
    if isinstance(message, ToolMessage):
        return ("Data", content)
    if isinstance(message, AIMessage):
        return ("Agent", content)
    return ("System", content)


def _update_stream_phase(run: dict[str, Any], chunk: dict[str, Any], selected_analysts: list[str]) -> None:
    sections = run.setdefault("stream_sections", {})
    selected = selected_analysts or ["market", "social", "news", "fundamentals"]
    parallel_analysts = run.get("analyst_execution_mode") == "parallel"
    active_names: list[str] = []

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue
        report_key = ANALYST_REPORT_MAP[analyst_key]
        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        if chunk.get(report_key):
            sections[report_key] = chunk[report_key]
        has_report = bool(sections.get(report_key))
        if has_report:
            _set_agent_status(run, agent_name, "completed")
            continue
        if parallel_analysts:
            active_names.append(agent_name)
            _set_agent_status(run, agent_name, "in_progress")
            continue
        if not active_names:
            active_names.append(agent_name)
            _set_agent_status(run, agent_name, "in_progress")
            continue
        _set_agent_status(run, agent_name, "pending")

    if active_names:
        if parallel_analysts:
            run["phase"] = f"分析师团队并行中 ({len(active_names)})"
        else:
            run["phase"] = f"{active_names[0]} 进行中"

    if chunk.get("investment_debate_state"):
        debate = chunk["investment_debate_state"]
        if debate.get("bull_history") or debate.get("bear_history"):
            run["phase"] = "Research Team 讨论中"
            _set_agent_status(run, "Bull Researcher", "in_progress")
            _set_agent_status(run, "Bear Researcher", "in_progress")
        if debate.get("judge_decision"):
            run["phase"] = "Research Manager 汇总中"
            _set_agent_status(run, "Bull Researcher", "completed")
            _set_agent_status(run, "Bear Researcher", "completed")
            _set_agent_status(run, "Research Manager", "completed")
            if run.get("agent_status", {}).get("Factor Manager") != "completed":
                _set_agent_status(run, "Factor Manager", "in_progress")

    factor_score = chunk.get("factor_score") if isinstance(chunk.get("factor_score"), dict) else {}
    alpha_result = chunk.get("alpha_mining_result") if isinstance(chunk.get("alpha_mining_result"), dict) else {}
    has_factor_result = _has_factor_runtime_result(factor_score, alpha_result)
    if has_factor_result:
        run["phase"] = "Factor Manager 生成因子评分"
        factor_already_completed = run.get("agent_status", {}).get("Factor Manager") == "completed"
        _set_agent_status(run, "Factor Manager", "completed")
        factor_detail = _build_factor_runtime_detail(
            {
                "factor_score": factor_score,
                "alpha_mining_result": alpha_result,
                "alpha_experience_summary": chunk.get("alpha_experience_summary", {}),
            }
        )
        run.setdefault("attachments", {})["factor_runtime_detail"] = factor_detail
        run.setdefault("attachments", {})["factor_runtime_source"] = "stream"
        run.setdefault("agent_outputs", {})["Factor Manager"] = _format_factor_manager_output(factor_detail)
        composite = factor_score.get("composite_score") if isinstance(factor_score, dict) else None
        signal = alpha_result.get("signal_score") if isinstance(alpha_result, dict) else None
        if not factor_already_completed:
            run.setdefault("logs", []).append({"kind": "stage", "text": "Factor Manager 已生成因子评分"})
            _append_event(
                run,
                "factor",
                "Factor Manager 已读取因子库并生成本次因子评分",
                {"composite_score": composite, "signal_score": signal},
            )

    if chunk.get("trader_investment_plan"):
        run["phase"] = "Trader 生成交易计划"
        _set_agent_status(run, "Trader", "completed")

    if chunk.get("risk_debate_state"):
        risk = chunk["risk_debate_state"]
        if risk.get("aggressive_history") or risk.get("conservative_history") or risk.get("neutral_history"):
            run["phase"] = "Risk Team 讨论中"
            _set_agent_status(run, "Aggressive Analyst", "in_progress")
            _set_agent_status(run, "Conservative Analyst", "in_progress")
            _set_agent_status(run, "Neutral Analyst", "in_progress")
        if risk.get("judge_decision"):
            run["phase"] = "Portfolio Manager 决策中"
            _set_agent_status(run, "Aggressive Analyst", "completed")
            _set_agent_status(run, "Conservative Analyst", "completed")
            _set_agent_status(run, "Neutral Analyst", "completed")
            _set_agent_status(run, "Portfolio Manager", "completed")


def _read_report_preview(report_file: Path | None) -> str:
    if report_file is None or not report_file.exists():
        return ""
    text = report_file.read_text(encoding="utf-8")
    return text[:12000]


def _run_real_analysis(run_id: str) -> None:
    run = RUNS[run_id]
    payload = run["payload"]
    user_id = _sanitize_user_id(str(run.get("user_id") or payload.get("user_id") or "local"))
    ticker = str(payload.get("ticker") or "").strip().upper()
    analysis_date = str(payload.get("analysis_date") or "").strip()
    asset_type = str(payload.get("asset_type") or "stock").strip().lower() or "stock"
    if _looks_like_crypto_ticker(ticker):
        asset_type = "crypto"
        payload["asset_type"] = "crypto"
    selected_analysts = [str(item).lower() for item in payload.get("analysts", []) if str(item).strip()]
    if asset_type == "crypto":
        selected_analysts = [item for item in selected_analysts if item != "fundamentals"]
        payload["analysts"] = selected_analysts or ["market", "social", "news"]

    slot_acquired = False
    metrics_handler = RunMetricsCallbackHandler(
        provider=str(payload.get("llm_provider") or ""),
        quick_model=str(payload.get("quick_think_llm") or ""),
        deep_model=str(payload.get("deep_think_llm") or ""),
    )
    run["metrics_handler"] = metrics_handler
    try:
        if _run_cancel_requested(run):
            _mark_run_cancelled(run, "[cancel] 任务已在启动前取消")
            return
        run["status"] = "queued"
        _update_phase(
            run,
            "排队等待执行资源",
            4,
            f"[queue] 等待执行槽 user={user_id} global={RUN_CONCURRENCY} per_user={RUN_USER_CONCURRENCY}",
        )
        while True:
            if _run_cancel_requested(run):
                _mark_run_cancelled(run, "[cancel] 任务在排队阶段已取消，未占用执行资源")
                return
            if _active_runs_for_user(user_id) >= RUN_USER_CONCURRENCY:
                time.sleep(0.25)
                continue
            if not RUN_SLOT.acquire(timeout=0.25):
                continue
            if _active_runs_for_user(user_id) >= RUN_USER_CONCURRENCY:
                RUN_SLOT.release()
                time.sleep(0.25)
                continue
            break
        slot_acquired = True
        run["slot_acquired"] = True
        _append_event(
            run,
            "queue",
            "已获得执行槽",
            {
                "active_runs": _run_queue_snapshot()["active_runs"],
                "user_active_runs": _active_runs_for_user(user_id),
            },
        )
        _persist_run_snapshot(run)
        if _run_cancel_requested(run):
            _mark_run_cancelled(run, "[cancel] 任务在启动执行前已取消")
            return
        run["status"] = "running"
        _append_event(run, "phase", "任务开始运行", {"phase": "running"})
        run["checkpoint_enabled"] = bool(payload.get("checkpoint_enabled"))
        run["checkpoint_available"] = (
            has_checkpoint(_checkpoint_data_dir(payload), ticker, analysis_date)
            if run["checkpoint_enabled"]
            else False
        )
        run["resume_hint"] = (
            "本次将从 checkpoint 恢复"
            if run["checkpoint_enabled"] and run["checkpoint_available"]
            else ("Checkpoint 已开启，但当前没有可恢复节点" if run["checkpoint_enabled"] else "Checkpoint 未开启")
        )
        _update_phase(run, "准备配置", 5, f"[config] ticker={ticker} asset_type={asset_type}")
        asset_diagnostic = _build_asset_type_diagnostic(ticker, asset_type)
        if asset_diagnostic:
            run["attachments"]["data_diagnostic"] = asset_diagnostic
            _append_log(run, f"[data] {asset_diagnostic}")

        config = _build_run_config(payload)
        run["analyst_execution_mode"] = (
            "parallel" if config.get("parallel_analysts") else "serial"
        )
        graph = TradingAgentsGraph(
            selected_analysts=selected_analysts or ["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
            callbacks=[metrics_handler],
        )

        _update_phase(
            run,
            "初始化图执行",
            12,
            f"[run] 正在初始化 {ticker} 的分析流程 analyst_mode={run['analyst_execution_mode']} concurrency={config.get('analyst_concurrency_limit', 1)}",
        )
        run["agent_status"] = _initial_agent_status(selected_analysts)

        past_context = graph.memory_log.get_past_context(ticker)
        init_agent_state = graph.propagator.create_initial_state(
            ticker,
            analysis_date,
            asset_type=asset_type,
            past_context=past_context,
            analysis_lookback_days=config.get("analysis_lookback_days", 30),
        )
        args = graph.propagator.get_graph_args(callbacks=[metrics_handler])
        if graph.config.get("checkpoint_enabled"):
            from tradingagents.graph.checkpointer import get_checkpointer, thread_id
            graph._checkpointer_ctx = get_checkpointer(graph.config["data_cache_dir"], ticker)
            saver = graph._checkpointer_ctx.__enter__()
            graph.graph = graph.workflow.compile(checkpointer=saver)
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = thread_id(ticker, str(analysis_date))

        _update_phase(run, "执行分析", 18, f"[run] 已进入 graph.stream({ticker}, {analysis_date})")

        trace: list[dict[str, Any]] = []
        seen_messages: set[str] = set()
        with bind_run_metrics_collector(metrics_handler):
            for chunk in graph.graph.stream(init_agent_state, **args):
                if _run_cancel_requested(run):
                    _refresh_runtime_metrics(run, metrics_handler)
                    _mark_run_cancelled(run, "[cancel] 当前 agent 调用返回后，任务已停止")
                    if graph.config.get("checkpoint_enabled") and graph._checkpointer_ctx is not None:
                        graph._checkpointer_ctx.__exit__(None, None, None)
                        graph._checkpointer_ctx = None
                        graph.graph = graph.workflow.compile()
                    return
                trace.append(chunk)
                _update_stream_phase(run, chunk, selected_analysts)
                _merge_agent_outputs_from_chunk(run, chunk)
                progress = min(58, 18 + len(trace) * 2)
                run["progress"] = progress
                run["elapsed"] = _now_elapsed(run["started_at"])

                for message in chunk.get("messages", []):
                    msg_id = getattr(message, "id", None)
                    if msg_id is not None:
                        if msg_id in seen_messages:
                            continue
                        seen_messages.add(msg_id)
                    msg_type, content = _classify_message_type(message)
                    if content and content.strip():
                        preview = content.strip().replace("\n", " ")
                        if len(preview) > 220:
                            preview = preview[:217] + "..."
                        run["logs"].append({
                            "kind": msg_type.lower(),
                            "text": preview,
                        })
                if chunk.get("market_report"):
                    run["logs"].append({"kind": "stage", "text": "Market Analyst 已完成"})
                    _append_event(run, "agent_done", "Market Analyst 已完成", {"agent": "Market Analyst"})
                if chunk.get("sentiment_report"):
                    run["logs"].append({"kind": "stage", "text": "Sentiment Analyst 已完成"})
                    _append_event(run, "agent_done", "Sentiment Analyst 已完成", {"agent": "Sentiment Analyst"})
                if chunk.get("news_report"):
                    run["logs"].append({"kind": "stage", "text": "News Analyst 已完成"})
                    _append_event(run, "agent_done", "News Analyst 已完成", {"agent": "News Analyst"})
                if chunk.get("fundamentals_report"):
                    run["logs"].append({"kind": "stage", "text": "Fundamentals Analyst 已完成"})
                    _append_event(run, "agent_done", "Fundamentals Analyst 已完成", {"agent": "Fundamentals Analyst"})
                if chunk.get("trader_investment_plan"):
                    run["logs"].append({"kind": "stage", "text": "Trader 已生成交易计划"})
                    _append_event(run, "agent_done", "Trader 已生成交易计划", {"agent": "Trader"})
                if chunk.get("final_trade_decision"):
                    run["logs"].append({"kind": "stage", "text": "Portfolio Manager 已给出最终决策"})
                    _append_event(run, "agent_done", "Portfolio Manager 已给出最终决策", {"agent": "Portfolio Manager"})
                _refresh_runtime_metrics(run, metrics_handler)
                _persist_run_snapshot(run)

        if _run_cancel_requested(run):
            _mark_run_cancelled(run, "[cancel] 图执行返回后已停止，跳过报告、回测和 Alpha Mining")
            if graph.config.get("checkpoint_enabled") and graph._checkpointer_ctx is not None:
                graph._checkpointer_ctx.__exit__(None, None, None)
                graph._checkpointer_ctx = None
                graph.graph = graph.workflow.compile()
            return

        final_state: dict[str, Any] = {}
        for chunk in trace:
            final_state.update(chunk)
        graph.curr_state = final_state
        final_state.setdefault("time_context", init_agent_state.get("time_context", {}))
        from tradingagents.core.data_snapshot import DataSnapshot
        final_state["data_snapshot"] = DataSnapshot.from_state(final_state).to_log_payload()
        _refresh_runtime_metrics(run, metrics_handler)
        final_state["run_metrics"] = run.get("runtime_metrics", {})
        graph.ticker = ticker
        graph._log_state(analysis_date, final_state)
        graph.memory_log.store_decision(
            ticker=ticker,
            trade_date=analysis_date,
            final_trade_decision=final_state["final_trade_decision"],
        )
        decision = graph.process_signal(final_state["final_trade_decision"])
        if graph.config.get("checkpoint_enabled") and graph._checkpointer_ctx is not None:
            clear_checkpoint(graph.config["data_cache_dir"], ticker, str(analysis_date))
            graph._checkpointer_ctx.__exit__(None, None, None)
            graph._checkpointer_ctx = None
            graph.graph = graph.workflow.compile()

        run["final_state"] = final_state
        run["decision"] = decision
        run["result"] = _result_summary_from_state(final_state, decision)
        run["attachments"]["data_diagnostic"] = (
            _build_asset_type_diagnostic(ticker, asset_type)
            or _build_data_availability_diagnostic(final_state)
        )
        output_language = str(payload.get("output_language") or "")
        run["agent_outputs"] = _extract_agent_outputs(final_state, output_language)
        run["report_sections"] = _extract_report_sections(final_state, output_language)
        run["attachments"]["factor_runtime_detail"] = _build_factor_runtime_detail(final_state)
        if final_state.get("factor_score") or final_state.get("alpha_mining_result"):
            factor_detail = run["attachments"]["factor_runtime_detail"]
            _set_agent_status(run, "Factor Manager", "completed")
            run["agent_outputs"]["Factor Manager"] = _format_factor_manager_output(factor_detail)

        report_root = None
        report_file = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if payload.get("save_report"):
            _update_phase(run, "保存报告", 60, "[report] 正在保存分析报告")
            report_root = _report_root_for_user(user_id) / f"{ticker}_{timestamp}"
            report_file = _save_report_to_disk(final_state, ticker, report_root, output_language)
            run["attachments"]["report_saved"] = True
            run["attachments"]["report_path"] = str(report_root)
            run["report_preview"] = _read_report_preview(report_file)
            run["report_file"] = str(report_file)
            _append_log(run, f"[report] 报告已保存到 {report_root}")
        else:
            run["report_preview"] = ""

        if payload.get("run_report_evaluation") and report_file is not None:
            if _run_cancel_requested(run):
                _mark_run_cancelled(run, "[cancel] 已取消，跳过报告评估")
                return
            reference_path_raw = str(payload.get("report_reference_path") or "").strip()
            if reference_path_raw:
                try:
                    reference_path = _resolve_reference_path(reference_path_raw, user_id)
                except ValueError as error:
                    run["attachments"]["evaluation_enabled"] = True
                    run["attachments"]["evaluation_summary"] = str(error)
                    _append_log(run, f"[evaluation] 跳过: {error}")
                    reference_path = None
                if reference_path is not None and reference_path.exists():
                    _update_phase(run, "报告评估", 72, f"[evaluation] 正在评估报告 against {reference_path}")
                    evaluator = ReportEvaluator(graph.quick_thinking_llm)
                    evaluation = evaluator.evaluate(
                        report_file.read_text(encoding="utf-8"),
                        _load_reference_text(reference_path),
                        topic=str(payload.get("report_topic") or f"{ticker} {analysis_date}"),
                    )
                    final_state["report_evaluation"] = evaluation.model_dump()
                    evaluation_file = _save_report_evaluation_to_disk(evaluation, report_root)
                    _append_report_evaluation_to_report(report_file, evaluation_file)
                    run["attachments"]["evaluation_enabled"] = True
                    run["attachments"]["evaluation_summary"] = (
                        f"Total Score {evaluation.total_score:.1f}/100 | {evaluation.verdict}"
                    )
                    run["report_preview"] = _read_report_preview(report_file)
                    _append_log(run, f"[evaluation] 报告评估已保存到 {evaluation_file}")
                elif reference_path is not None:
                    run["attachments"]["evaluation_enabled"] = True
                    run["attachments"]["evaluation_summary"] = f"参考文件不存在: {reference_path}"
                    _append_log(run, f"[evaluation] 跳过，参考文件不存在: {reference_path}")

        if payload.get("run_backtest"):
            if _run_cancel_requested(run):
                _mark_run_cancelled(run, "[cancel] 已取消，跳过回测")
                return
            _update_phase(run, "运行回测", 82, "[backtest] 正在执行 backtest")
            initial_capital = _parse_initial_capital_input(str(payload.get("backtest_initial_capital") or "1.0"))
            holding_days_list = _parse_holding_days_input(str(payload.get("backtest_holding_days") or "5,10,20"))
            backtest_ticker = _normalize_market_data_ticker(ticker, asset_type)
            if backtest_ticker != ticker:
                _append_log(run, f"[backtest] 已将 {ticker} 标准化为行情代码 {backtest_ticker}")
            backtest_benchmark = graph._resolve_benchmark(backtest_ticker)
            scenario = BacktestScenario(
                ticker=backtest_ticker,
                trade_date=analysis_date,
                asset_type=asset_type,
            )
            summary_results: list[tuple[int, Any]] = []
            backtest_save_dir = report_root / "6_backtests" if report_root is not None else None
            for holding_days in holding_days_list:
                result = graph.run_backtest_from_final_states(
                    [scenario],
                    [final_state],
                    holding_days=holding_days,
                    initial_capital=initial_capital,
                )
                summary_results.append((holding_days, result))
                if backtest_save_dir is not None:
                    _save_backtest_result_to_disk(
                        result,
                        ticker,
                        analysis_date,
                        holding_days,
                        backtest_save_dir,
                    )
            if backtest_save_dir is not None:
                summary_file = _save_backtest_summary_to_disk(
                    summary_results,
                    ticker,
                    analysis_date,
                    backtest_save_dir,
                )
                if report_file is not None:
                    _append_backtest_summary_to_report(report_file, summary_file)
                    run["report_preview"] = _read_report_preview(report_file)
            metrics_preview = []
            backtest_detail = []
            for holding_days, result in summary_results:
                backtest_detail.append(
                    _backtest_result_payload(
                        holding_days,
                        result,
                        ticker=backtest_ticker,
                        trade_date=analysis_date,
                        asset_type=asset_type,
                        benchmark=backtest_benchmark,
                    )
                )
                if result.trades:
                    trade = result.trades[0]
                    metrics_preview.append(
                        f"{holding_days}d: return {trade.executed_return:.2%}, alpha {trade.executed_alpha_return:.2%}"
                    )
                else:
                    metrics_preview.append(f"{holding_days}d: no resolved future price data")
            run["attachments"]["backtest_enabled"] = True
            run["attachments"]["backtest_summary"] = " | ".join(metrics_preview)
            run["attachments"]["backtest_detail"] = backtest_detail
            _append_log(run, "[backtest] 回测已完成")

        if payload.get("run_alpha_mining"):
            if _run_cancel_requested(run):
                _mark_run_cancelled(run, "[cancel] 已取消，跳过 Alpha Mining")
                return
            _update_phase(run, "完成后更新因子库", 90, "[alpha] 正在将本次分析经验写入因子库")
            alpha_source = (
                Path(config["results_dir"])
                / ticker
                / "TradingAgentsStrategy_logs"
                / f"full_states_log_{analysis_date}.json"
            )
            registry_file, history_file, alpha_summary = _run_alpha_mining_for_source(alpha_source)
            final_state["alpha_experience_summary"] = alpha_summary
            run["attachments"]["alpha_mining_enabled"] = True
            run["attachments"]["alpha_mining_summary"] = (
                f"已更新因子库 registry={registry_file.name} | history={history_file.name}"
            )
            run["attachments"]["alpha_mining_detail"] = {
                "registry_file": str(registry_file),
                "history_file": str(history_file),
                "summary": alpha_summary,
                "selected_alpha": final_state.get("alpha_mining_result", {}).get("selected_alpha", {}),
                "signal_score": final_state.get("alpha_mining_result", {}).get("signal_score", 0.0),
                "confidence": final_state.get("alpha_mining_result", {}).get("confidence", 0.0),
            }
            _append_log(run, f"[alpha] Alpha mining 完成: {registry_file}")

        if _run_cancel_requested(run):
            _mark_run_cancelled(run, "[cancel] 已取消，跳过完成态写入")
            return
        _update_phase(run, "完成", 100, f"[done] {ticker} 分析完成")
        run["status"] = "completed"
        run["elapsed"] = _now_elapsed(run["started_at"])
        run["updated_at"] = datetime.datetime.now().isoformat()
        run["checkpoint_available"] = False
        run["resume_hint"] = "本次任务已完成，checkpoint 已清理"
        for agent in list(run.get("agent_status", {}).keys()):
            _set_agent_status(run, agent, "completed")
        _refresh_runtime_metrics(run, metrics_handler)
        _append_event(run, "done", f"{ticker} 分析完成", {"ticker": ticker})
        _persist_run_snapshot(run)
    except Exception as error:
        if _run_cancel_requested(run):
            _mark_run_cancelled(run, f"[cancel] 任务取消后执行线程已退出: {type(error).__name__}: {error}")
            return
        run["status"] = "failed"
        run["phase"] = "失败"
        run["progress"] = 100
        run["elapsed"] = _now_elapsed(run["started_at"])
        run["logs"].append(f"[error] {type(error).__name__}: {error}")
        run["error_message"] = f"{type(error).__name__}: {error}"
        run["checkpoint_available"] = (
            has_checkpoint(_checkpoint_data_dir(payload), ticker, analysis_date)
            if run.get("checkpoint_enabled")
            else False
        )
        run["resume_hint"] = (
            "任务失败，可尝试从 checkpoint 恢复"
            if run["checkpoint_available"]
            else "任务失败，但当前没有可恢复 checkpoint"
        )
        run["result"] = {
            "rating": "Failed",
            "confidence": 0.0,
            "position": "N/A",
            "summary": str(error),
        }
        run["updated_at"] = datetime.datetime.now().isoformat()
        _refresh_runtime_metrics(run, metrics_handler)
        _append_event(run, "error", run["error_message"])
        _persist_run_snapshot(run)
    finally:
        if slot_acquired:
            _release_run_slot(run, "已释放执行槽")


class TradingAgentsWorkbenchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _auth_session_or_401(self) -> dict[str, Any] | None:
        session = _current_auth_session(self)
        if session:
            return session
        self._send_json(
            401,
            {
                "error": "authentication_required",
                "message": "请先登录 TradingAgents Workbench。",
            },
        )
        return None

    def _send_markdown_file(self, file_path: Path, download_name: str) -> None:
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/auth/session":
            session = _current_auth_session(self)
            if not session:
                self._send_json(200, {"authenticated": False})
                return
            self._send_json(
                200,
                _public_auth_payload(
                    str(session.get("username") or ""),
                    _sanitize_user_id(str(session.get("user_id") or "")),
                    str(session.get("role") or "user"),
                ),
            )
            return

        if parsed.path == "/api/auth/challenge":
            self._send_json(200, _create_auth_challenge())
            return

        if parsed.path.startswith("/api/") and self._auth_session_or_401() is None:
            return

        if parsed.path == "/api/meta":
            session = _current_auth_session(self)
            queue_snapshot = _run_queue_snapshot()
            self._send_json(
                200,
                {
                    "mode": "python-bridge-real",
                    "status": "ok",
                    "multi_user": True,
                    "auth": _public_auth_payload(
                        str(session.get("username") or ""),
                        _sanitize_user_id(str(session.get("user_id") or "")),
                        str(session.get("role") or "user"),
                    ) if session else {"authenticated": False},
                    **queue_snapshot,
                },
            )
            return

        if parsed.path == "/api/admin/users":
            session = _current_auth_session(self)
            if str((session or {}).get("role") or "") != "admin":
                self._send_json(403, {"error": "admin_required", "message": "需要管理员权限。"})
                return
            self._send_json(200, _admin_users_payload())
            return

        if parsed.path == "/api/health":
            self._send_json(200, _health_payload(_request_user_id(self)))
            return

        if parsed.path == "/api/settings":
            user_id = _request_user_id(self)
            self._send_json(
                200,
                {
                    "settings": _load_workbench_settings(user_id),
                    "effective": {
                        "llm_timeout": _health_payload(user_id)["llm_timeout"],
                        "llm_max_retries": _health_payload(user_id)["llm_max_retries"],
                    },
                },
            )
            return

        if parsed.path == "/api/model-options":
            payload = {
                provider: {
                    mode: [{"label": label, "value": value} for label, value in options]
                    for mode, options in mode_map.items()
                }
                for provider, mode_map in MODEL_OPTIONS.items()
            }
            self._send_json(200, payload)
            return

        if parsed.path == "/api/alpha-factors":
            query = parse_qs(parsed.query)
            ticker = str((query.get("ticker") or [""])[0]).strip().upper()
            user_id = _request_user_id(self)
            self._send_json(200, _load_alpha_factors_for_ticker(ticker, user_id=user_id))
            return

        if parsed.path == "/api/history":
            query = parse_qs(parsed.query)
            limit = int((query.get("limit") or ["50"])[0] or "50")
            user_id = _request_user_id(self)
            rows = _load_persisted_history(user_id, limit=max(1, min(limit, 200)))
            self._send_json(200, {"items": rows, "count": len(rows), "queue": _run_queue_snapshot()})
            return

        if parsed.path == "/api/debug/runs":
            user_id = _request_user_id(self)
            rows = [
                _public_run_payload(run)
                for run in RUNS.values()
                if _sanitize_user_id(str(run.get("user_id") or "local")) == user_id
            ]
            rows.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            self._send_json(200, {"items": rows, "count": len(rows), "queue": _run_queue_snapshot()})
            return

        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/report"):
            parts = parsed.path.strip("/").split("/")
            run_id = parts[2] if len(parts) >= 4 else ""
            run = RUNS.get(run_id)
            if run is None:
                self._send_json(
                    404,
                    {
                        "error": "run_not_found",
                        "message": "任务不在当前服务进程内，可能服务已重启或该任务只存在于浏览器历史。",
                    },
                )
                return
            if _sanitize_user_id(str(run.get("user_id") or "local")) != _request_user_id(self):
                self._send_json(
                    403,
                    {
                        "error": "user_mismatch",
                        "message": "当前浏览器用户不能访问其他用户的任务。",
                    },
                )
                return
            report_file = Path(str(run.get("report_file") or "")).expanduser()
            if not report_file.exists() or not report_file.is_file():
                self._send_json(404, {"error": "report_not_found"})
                return
            ticker = str(run.get("payload", {}).get("ticker") or "report").strip().upper() or "report"
            analysis_date = str(run.get("payload", {}).get("analysis_date") or "").strip()
            download_name = f"{ticker}_{analysis_date}_complete_report.md" if analysis_date else f"{ticker}_complete_report.md"
            self._send_markdown_file(report_file, download_name)
            return

        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[-1]
            run = RUNS.get(run_id)
            if run is None:
                persisted = _load_persisted_run(run_id, _request_user_id(self))
                if persisted is not None:
                    self._send_json(200, persisted)
                    return
                self._send_json(404, {"error": "run_not_found"})
                return
            if _sanitize_user_id(str(run.get("user_id") or "local")) != _request_user_id(self):
                self._send_json(404, {"error": "run_not_found"})
                return

            _refresh_live_run_status(run, persist=run.get("status") in {"queued", "running", "cancelling"})
            self._send_json(200, _public_run_payload(run))
            return

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError as error:
            self._send_json(400, {"error": "invalid_json", "message": str(error)})
            return
        if not isinstance(payload, dict):
            payload = {}

        if parsed.path in {"/api/auth/login", "/api/auth/register"}:
            username = str(payload.get("username") or "")
            password = str(payload.get("password") or "")
            challenge_id = str(payload.get("challenge_id") or "")
            challenge_answer = payload.get("challenge_answer") or {}
            if not _verify_auth_challenge(challenge_id, challenge_answer):
                self._send_json(
                    400,
                    {
                        "error": "challenge_failed",
                        "message": "安全验证失败或已过期，请重新输入。",
                    },
                )
                return
            try:
                if parsed.path == "/api/auth/register":
                    user = _register_auth_user(username, password)
                else:
                    user, error_message = _authenticate_user(username, password)
                    if user is None:
                        self._send_json(
                            401,
                            {
                                "error": "invalid_credentials",
                                "message": error_message or "用户名或密码不正确。",
                            },
                        )
                        return
                token = _create_auth_session(user)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        **_public_auth_payload(
                            str(user["username"]),
                            _sanitize_user_id(str(user["user_id"])),
                            str(user.get("role") or "user"),
                        ),
                    },
                    headers={"Set-Cookie": _auth_cookie(token)},
                )
            except ValueError as error:
                self._send_json(400, {"error": "auth_failed", "message": str(error)})
            return

        if parsed.path == "/api/auth/logout":
            _delete_auth_session(self)
            self._send_json(
                200,
                {"ok": True, "authenticated": False},
                headers={"Set-Cookie": _clear_auth_cookie()},
            )
            return

        if parsed.path.startswith("/api/") and self._auth_session_or_401() is None:
            return

        if parsed.path in {"/api/admin/users/update", "/api/admin/users/reset-password", "/api/admin/users/delete"}:
            session = _current_auth_session(self)
            if str((session or {}).get("role") or "") != "admin":
                self._send_json(403, {"error": "admin_required", "message": "需要管理员权限。"})
                return
            actor = _normalize_username(str((session or {}).get("username") or ""))
            target_username = str(payload.get("username") or "")
            try:
                if parsed.path.endswith("/update"):
                    _admin_update_user(
                        actor,
                        target_username,
                        {
                            "role": payload.get("role"),
                            "disabled": payload.get("disabled"),
                            "unlock": bool(payload.get("unlock")),
                        },
                    )
                elif parsed.path.endswith("/reset-password"):
                    _admin_reset_password(actor, target_username, str(payload.get("new_password") or ""))
                else:
                    _admin_delete_user(actor, target_username)
            except ValueError as error:
                self._send_json(400, {"error": "admin_update_failed", "message": str(error)})
                return
            self._send_json(200, {"ok": True, **_admin_users_payload()})
            return

        if parsed.path == "/api/discover-models":
            try:
                payload["user_id"] = _request_user_id(self, payload)
                discovered = _discover_remote_models(payload)
            except Exception as error:
                self._send_json(400, {"error": "discover_failed", "message": str(error)})
                return
            self._send_json(200, discovered)
            return

        if parsed.path == "/api/clear-checkpoint":
            payload["user_id"] = _request_user_id(self, payload)
            ticker = str(payload.get("ticker", "")).strip().upper()
            analysis_date = str(payload.get("analysis_date", "")).strip()
            clear_checkpoint(_checkpoint_data_dir(payload), ticker, analysis_date)
            self._send_json(200, {"ok": True})
            return

        if parsed.path == "/api/cancel-run":
            request_user_id = _request_user_id(self, payload)
            run_id = str(payload.get("run_id", "")).strip()
            run = RUNS.get(run_id)
            if not run:
                self._send_json(
                    404,
                    {
                        "error": "run_not_found",
                        "message": "任务不在当前服务进程内，可能服务已重启或该任务只存在于浏览器历史。",
                    },
                )
                return
            if _sanitize_user_id(str(run.get("user_id") or "local")) != request_user_id:
                self._send_json(
                    403,
                    {
                        "error": "user_mismatch",
                        "message": "当前浏览器用户不能取消其他用户的任务。",
                    },
                )
                return
            if run.get("status") in {"queued", "running", "cancelling"}:
                _request_run_cancellation(
                    run,
                    "[cancel] 已收到取消请求；若当前 LLM/数据调用正在阻塞，后台线程会在调用返回后回收执行槽",
                )
            elif run.get("status") in {"completed", "failed", "cancelled"}:
                _append_log(run, f"[cancel] 任务已处于 {run.get('status')}，无需取消")
            run["updated_at"] = datetime.datetime.now().isoformat()
            run["metrics"] = _build_metrics_snapshot(run)
            self._send_json(200, {"ok": True, "run": _public_run_payload(run)})
            return

        if parsed.path == "/api/restart-workbench":
            request_user_id = _request_user_id(self, payload)
            confirmation = str(payload.get("confirm") or "").strip()
            if confirmation != "RESTART_WORKBENCH":
                self._send_json(
                    400,
                    {
                        "error": "confirmation_required",
                        "message": "需要确认令牌才能强制重启 Workbench。",
                    },
                )
                return
            run_id = str(payload.get("run_id", "")).strip()
            target_run = RUNS.get(run_id) if run_id else None
            if target_run and _sanitize_user_id(str(target_run.get("user_id") or "local")) != request_user_id:
                self._send_json(
                    403,
                    {
                        "error": "user_mismatch",
                        "message": "当前浏览器用户不能强制重启其他用户的任务。",
                    },
                )
                return
            affected = _mark_active_runs_for_workbench_restart(
                "[restart] 用户触发 Workbench 强制重启；当前阻塞任务已硬取消"
            )
            response = {
                "ok": True,
                "message": "Workbench 正在强制重启；Docker restart policy 会自动拉起服务。",
                "affected_run_ids": [str(run.get("run_id") or "") for run in affected],
                "run": _public_run_payload(target_run) if target_run else None,
            }
            self._send_json(202, response)
            _schedule_workbench_restart()
            return

        if parsed.path == "/api/delete-run":
            request_user_id = _request_user_id(self, payload)
            run_id = str(payload.get("run_id", "")).strip()
            live_run = RUNS.get(run_id)
            if live_run and _sanitize_user_id(str(live_run.get("user_id") or "local")) != request_user_id:
                self._send_json(403, {"error": "user_mismatch"})
                return
            result = _delete_persisted_run(
                run_id,
                request_user_id,
                delete_artifacts=bool(payload.get("delete_artifacts")),
            )
            status = 200 if result.get("ok") else 500
            self._send_json(status, result)
            return

        if parsed.path == "/api/settings":
            request_user_id = _request_user_id(self, payload)
            settings = _save_workbench_settings(
                request_user_id,
                {
                    "llm_timeout": max(15, min(600, int(payload.get("llm_timeout") or 90))),
                    "llm_max_retries": max(0, min(5, int(payload.get("llm_max_retries") or 2))),
                },
            )
            self._send_json(200, {"ok": True, "settings": settings, "health": _health_payload(request_user_id)})
            return

        if parsed.path != "/api/runs":
            self._send_json(404, {"error": "not_found"})
            return

        user_id = _request_user_id(self, payload)
        payload["user_id"] = user_id
        ticker = str(payload.get("ticker", "")).strip().upper()
        analysis_date = str(payload.get("analysis_date", "")).strip()
        payload["ticker"] = ticker
        payload["analysis_date"] = analysis_date
        if _looks_like_crypto_ticker(ticker):
            payload["asset_type"] = "crypto"
            payload["analysts"] = [
                str(item).lower()
                for item in payload.get("analysts", [])
                if str(item).strip().lower() != "fundamentals"
            ] or ["market", "social", "news"]

        persisted_env_path = _persist_api_key(payload)
        run_id = uuid.uuid4().hex[:8]
        started_at = time.time()
        attachments = {
            "report_saved": bool(payload.get("save_report")),
            "report_path": "",
            "evaluation_enabled": bool(payload.get("run_report_evaluation")),
            "evaluation_summary": "",
            "backtest_enabled": bool(payload.get("run_backtest")),
            "backtest_summary": "",
            "backtest_detail": [],
            "alpha_mining_enabled": bool(payload.get("run_alpha_mining")),
            "alpha_mining_summary": "",
            "alpha_mining_detail": None,
            "factor_runtime_detail": None,
            "data_diagnostic": _build_asset_type_diagnostic(ticker, str(payload.get("asset_type") or "stock")),
        }
        logs = [
            {"kind": "system", "text": "请求已被服务端接收"},
            {"kind": "config", "text": f"ticker={ticker} provider={payload.get('llm_provider', '')}"},
            {
                "kind": "config",
                "text": (
                    "role_models="
                    f"analysis:{payload.get('analysis_think_llm') or payload.get('quick_think_llm') or ''} "
                    f"debate:{payload.get('debate_think_llm') or payload.get('quick_think_llm') or ''} "
                    f"decision:{payload.get('decision_think_llm') or payload.get('deep_think_llm') or ''}"
                ),
            },
            {"kind": "config", "text": f"analysis_lookback_days={payload.get('analysis_lookback_days', 30)}"},
            {"kind": "config", "text": f"output_language={payload.get('output_language', 'English')}"},
        ]
        if persisted_env_path is not None:
            if str(persisted_env_path).startswith("当前任务"):
                logs.append({"kind": "env", "text": "API key 将仅用于当前任务，不写入公共 .env"})
            else:
                logs.append({"kind": "env", "text": f"已将 API key 写入 {persisted_env_path}"})

        run = {
            "run_id": run_id,
            "user_id": user_id,
            "status": "queued",
            "phase": "排队中",
            "progress": 0,
            "elapsed": "00:00",
            "started_at": started_at,
            "payload": payload,
            "logs": logs,
            "result": None,
            "attachments": attachments,
            "report_preview": "",
            "final_state": None,
            "decision": None,
            "agent_status": _initial_agent_status([str(item).lower() for item in payload.get("analysts", []) if str(item).strip()]),
            "agent_timings": {},
            "agent_outputs": {},
            "runtime_metrics": {},
            "checkpoint_enabled": bool(payload.get("checkpoint_enabled")),
            "checkpoint_available": (
                has_checkpoint(_checkpoint_data_dir(payload), ticker, analysis_date)
                if bool(payload.get("checkpoint_enabled"))
                else False
            ),
            "resume_hint": (
                "本次将从 checkpoint 恢复"
                if bool(payload.get("checkpoint_enabled")) and has_checkpoint(_checkpoint_data_dir(payload), ticker, analysis_date)
                else ("Checkpoint 已开启，但当前没有可恢复节点" if bool(payload.get("checkpoint_enabled")) else "Checkpoint 未开启")
            ),
            "cancel_requested": False,
            "slot_acquired": False,
            "events": [],
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
        }
        _append_event(run, "created", "任务已创建", {"ticker": ticker, "analysis_date": analysis_date})
        RUNS[run_id] = run
        _persist_run_snapshot(run)

        worker = threading.Thread(target=_run_real_analysis, args=(run_id,), daemon=True)
        run["worker_thread"] = worker
        worker.start()

        self._send_json(201, _public_run_payload(run))


def main() -> None:
    host = os.environ.get("TRADINGAGENTS_WORKBENCH_HOST", "127.0.0.1")
    port = int(os.environ.get("TRADINGAGENTS_WORKBENCH_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), TradingAgentsWorkbenchHandler)
    print(f"TradingAgents workbench running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
