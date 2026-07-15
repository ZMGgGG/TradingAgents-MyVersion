from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from typing import Any, Generator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult


# Static, best-effort pricing table. Unknown models still report usage, but
# omit cost rather than pretending we know current vendor pricing.
MODEL_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-5.5-pro": (30.0, 180.0),
}

_CURRENT_COLLECTOR: ContextVar["RunMetricsCallbackHandler | None"] = ContextVar(
    "tradingagents_run_metrics_collector",
    default=None,
)


def _empty_model_usage() -> dict[str, Any]:
    return {
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "estimated_cost_usd": None,
        "pricing_available": False,
    }


def _coerce_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _usage_from_generation(generation: Any) -> tuple[int, int]:
    message = getattr(generation, "message", None)
    usage = None
    if isinstance(message, AIMessage):
        usage = getattr(message, "usage_metadata", None)
        if usage:
            return (
                _coerce_int(usage.get("input_tokens")),
                _coerce_int(usage.get("output_tokens")),
            )
        response_metadata = getattr(message, "response_metadata", {}) or {}
        token_usage = response_metadata.get("token_usage") or response_metadata.get("usage")
        if token_usage:
            return (
                _coerce_int(
                    token_usage.get("prompt_tokens")
                    or token_usage.get("input_tokens")
                ),
                _coerce_int(
                    token_usage.get("completion_tokens")
                    or token_usage.get("output_tokens")
                ),
            )
    return 0, 0


def _model_from_generation(generation: Any) -> str:
    message = getattr(generation, "message", None)
    if isinstance(message, AIMessage):
        response_metadata = getattr(message, "response_metadata", {}) or {}
        for key in ("model_name", "model", "model_id"):
            value = response_metadata.get(key)
            if value:
                return str(value)
    generation_info = getattr(generation, "generation_info", None) or {}
    for key in ("model_name", "model", "model_id"):
        value = generation_info.get(key)
        if value:
            return str(value)
    return "unknown"


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float | None:
    pricing = MODEL_PRICING_USD_PER_1M.get(model)
    if not pricing:
        return None
    input_price, output_price = pricing
    return (tokens_in / 1_000_000.0 * input_price) + (
        tokens_out / 1_000_000.0 * output_price
    )


class RunMetricsCallbackHandler(BaseCallbackHandler):
    """Collect run-level LLM, tool, token, retry, cost, and vendor metrics."""

    def __init__(
        self,
        *,
        provider: str = "",
        quick_model: str = "",
        deep_model: str = "",
    ) -> None:
        super().__init__()
        self.provider = provider
        self.quick_model = quick_model
        self.deep_model = deep_model
        self._lock = threading.Lock()
        self._started_at = monotonic()
        self.llm_calls = 0
        self.tool_calls = 0
        self.retry_count = 0
        self.llm_errors = 0
        self.tool_errors = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.tool_counts: dict[str, int] = {}
        self.model_usage: dict[str, dict[str, Any]] = {}
        self.vendor_attempts = 0
        self.vendor_successes = 0
        self.vendor_fallbacks = 0
        self.vendor_failures = 0
        self.vendor_by_method: dict[str, dict[str, int]] = {}
        self.active_llm_calls: dict[str, dict[str, Any]] = {}
        self.llm_call_sequence = 0
        self.last_llm_event: dict[str, Any] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        prompt_chars = sum(len(str(prompt or "")) for prompt in prompts or [])
        self._record_llm_start(serialized, prompt_chars, kwargs)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        message_chars = 0
        for batch in messages or []:
            for message in batch or []:
                message_chars += len(str(getattr(message, "content", message) or ""))
        self._record_llm_start(serialized, message_chars, kwargs)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id") or "")
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            self._record_llm_finish(run_id, "end")
            return

        tokens_in, tokens_out = _usage_from_generation(generation)
        model = _model_from_generation(generation)
        cost = _estimate_cost(model, tokens_in, tokens_out)
        with self._lock:
            self.tokens_in += tokens_in
            self.tokens_out += tokens_out
            usage = self.model_usage.setdefault(model, _empty_model_usage())
            usage["llm_calls"] += 1
            usage["tokens_in"] += tokens_in
            usage["tokens_out"] += tokens_out
            if cost is not None:
                usage["pricing_available"] = True
                usage["estimated_cost_usd"] = (
                    float(usage["estimated_cost_usd"] or 0.0) + cost
                )
            self._record_llm_finish_locked(run_id, "end", model=model)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id") or "")
        with self._lock:
            self.llm_errors += 1
            self._record_llm_finish_locked(
                run_id,
                "error",
                error=f"{type(error).__name__}: {error}",
            )

    def on_retry(self, retry_state: Any, **kwargs: Any) -> None:
        with self._lock:
            self.retry_count += 1

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        tool_name = str(serialized.get("name") or serialized.get("id") or "unknown")
        with self._lock:
            self.tool_calls += 1
            self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        with self._lock:
            self.tool_errors += 1

    def _record_llm_start(
        self,
        serialized: dict[str, Any],
        input_chars: int,
        kwargs: dict[str, Any],
    ) -> None:
        run_id = str(kwargs.get("run_id") or "")
        invocation = kwargs.get("invocation_params") or {}
        model = (
            invocation.get("model")
            or invocation.get("model_name")
            or serialized.get("name")
            or serialized.get("id")
            or "unknown"
        )
        with self._lock:
            self.llm_calls += 1
            self.llm_call_sequence += 1
            call_id = run_id or f"llm-{self.llm_call_sequence}"
            self.active_llm_calls[call_id] = {
                "id": call_id,
                "sequence": self.llm_call_sequence,
                "model": str(model),
                "input_chars": max(0, int(input_chars or 0)),
                "started_at_offset_seconds": round(monotonic() - self._started_at, 3),
                "_started_at": monotonic(),
            }
            self.last_llm_event = {
                "event": "start",
                "id": call_id,
                "sequence": self.llm_call_sequence,
                "model": str(model),
                "elapsed_wall_seconds": round(monotonic() - self._started_at, 3),
            }

    def _record_llm_finish(self, run_id: str, event: str) -> None:
        with self._lock:
            self._record_llm_finish_locked(run_id, event)

    def _record_llm_finish_locked(
        self,
        run_id: str,
        event: str,
        *,
        model: str = "",
        error: str = "",
    ) -> None:
        call_id = run_id or ""
        call = self.active_llm_calls.pop(call_id, None) if call_id else None
        if call is None and self.active_llm_calls:
            call_id = sorted(
                self.active_llm_calls,
                key=lambda key: self.active_llm_calls[key].get("sequence", 0),
            )[0]
            call = self.active_llm_calls.pop(call_id, None)
        elapsed = 0.0
        if call is not None:
            elapsed = monotonic() - float(call.get("_started_at") or monotonic())
        self.last_llm_event = {
            "event": event,
            "id": call_id,
            "sequence": call.get("sequence") if call else None,
            "model": model or (call.get("model") if call else "unknown"),
            "duration_seconds": round(elapsed, 3),
            "elapsed_wall_seconds": round(monotonic() - self._started_at, 3),
        }
        if error:
            self.last_llm_event["error"] = error

    def record_vendor_event(
        self,
        *,
        event: str,
        method: str,
        vendor: str,
    ) -> None:
        with self._lock:
            if event == "attempt":
                self.vendor_attempts += 1
            elif event == "success":
                self.vendor_successes += 1
            elif event == "fallback":
                self.vendor_fallbacks += 1
            elif event == "failure":
                self.vendor_failures += 1

            method_row = self.vendor_by_method.setdefault(
                method,
                {
                    "attempts": 0,
                    "successes": 0,
                    "fallbacks": 0,
                    "failures": 0,
                },
            )
            key = {
                "attempt": "attempts",
                "success": "successes",
                "fallback": "fallbacks",
                "failure": "failures",
            }.get(event)
            if key:
                method_row[key] += 1
            vendor_key = f"vendor:{vendor}"
            method_row[vendor_key] = method_row.get(vendor_key, 0) + 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            estimated_cost = 0.0
            pricing_available = False
            model_usage = {}
            for model, usage in self.model_usage.items():
                copied = dict(usage)
                if copied["estimated_cost_usd"] is not None:
                    pricing_available = True
                    estimated_cost += float(copied["estimated_cost_usd"])
                    copied["estimated_cost_usd"] = round(
                        float(copied["estimated_cost_usd"]),
                        6,
                    )
                model_usage[model] = copied

            return {
                "provider": self.provider,
                "quick_model": self.quick_model,
                "deep_model": self.deep_model,
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "retry_count": self.retry_count,
                "llm_errors": self.llm_errors,
                "tool_errors": self.tool_errors,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "estimated_cost_usd": (
                    round(estimated_cost, 6) if pricing_available else None
                ),
                "pricing_available": pricing_available,
                "pricing_note": (
                    "estimated from static per-1M-token table"
                    if pricing_available
                    else "pricing unavailable for selected model(s)"
                ),
                "tool_counts": dict(self.tool_counts),
                "model_usage": model_usage,
                "vendor_attempts": self.vendor_attempts,
                "vendor_successes": self.vendor_successes,
                "vendor_fallbacks": self.vendor_fallbacks,
                "vendor_failures": self.vendor_failures,
                "vendor_by_method": {
                    method: dict(row)
                    for method, row in self.vendor_by_method.items()
                },
                "active_llm_calls": [
                    {
                        key: value
                        for key, value in call.items()
                        if not key.startswith("_")
                    }
                    | {
                        "elapsed_seconds": round(
                            monotonic() - float(call.get("_started_at") or monotonic()),
                            3,
                        )
                    }
                    for call in sorted(
                        self.active_llm_calls.values(),
                        key=lambda item: item.get("sequence", 0),
                    )
                ],
                "last_llm_event": dict(self.last_llm_event),
                "elapsed_wall_seconds": round(monotonic() - self._started_at, 3),
            }


@contextmanager
def bind_run_metrics_collector(
    collector: RunMetricsCallbackHandler | None,
) -> Generator[None, None, None]:
    token = _CURRENT_COLLECTOR.set(collector)
    try:
        yield
    finally:
        _CURRENT_COLLECTOR.reset(token)


def record_vendor_metric(event: str, method: str, vendor: str) -> None:
    collector = _CURRENT_COLLECTOR.get()
    if collector is None:
        return
    collector.record_vendor_event(event=event, method=method, vendor=vendor)
