import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from tradingagents.core.run_metrics import (
    RunMetricsCallbackHandler,
    bind_run_metrics_collector,
    record_vendor_metric,
)


@pytest.mark.unit
def test_run_metrics_collects_tokens_and_estimated_cost():
    handler = RunMetricsCallbackHandler(
        provider="openai",
        quick_model="gpt-5.5-pro",
        deep_model="gpt-5.5-pro",
    )
    handler.on_chat_model_start({}, [[]])
    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                        message=AIMessage(
                            content="ok",
                            usage_metadata={"input_tokens": 1000, "output_tokens": 2000, "total_tokens": 3000},
                            response_metadata={"model_name": "gpt-5.5-pro"},
                        )
                )
            ]
        ]
    )

    handler.on_llm_end(response)
    metrics = handler.get_metrics()

    assert metrics["llm_calls"] == 1
    assert metrics["tokens_in"] == 1000
    assert metrics["tokens_out"] == 2000
    assert metrics["pricing_available"] is True
    assert metrics["estimated_cost_usd"] == pytest.approx(0.39)
    assert metrics["model_usage"]["gpt-5.5-pro"]["estimated_cost_usd"] == pytest.approx(0.39)


@pytest.mark.unit
def test_run_metrics_records_tool_retry_and_vendor_events():
    handler = RunMetricsCallbackHandler(provider="qwen-cn")

    handler.on_tool_start({"name": "get_news"}, "")
    handler.on_retry(object())
    with bind_run_metrics_collector(handler):
        record_vendor_metric("attempt", "get_news", "akshare_cn")
        record_vendor_metric("fallback", "get_news", "akshare_cn")
        record_vendor_metric("attempt", "get_news", "yfinance")
        record_vendor_metric("success", "get_news", "yfinance")

    metrics = handler.get_metrics()

    assert metrics["tool_calls"] == 1
    assert metrics["tool_counts"]["get_news"] == 1
    assert metrics["retry_count"] == 1
    assert metrics["vendor_attempts"] == 2
    assert metrics["vendor_fallbacks"] == 1
    assert metrics["vendor_successes"] == 1
    assert metrics["vendor_by_method"]["get_news"]["fallbacks"] == 1


@pytest.mark.unit
def test_workbench_metrics_snapshot_includes_agent_timings():
    from frontend.server import _build_metrics_snapshot, _set_agent_status

    run = {"agent_status": {}, "logs": [], "report_sections": {}, "runtime_metrics": {}}
    _set_agent_status(run, "Market Analyst", "in_progress")
    _set_agent_status(run, "Market Analyst", "completed")

    metrics = _build_metrics_snapshot(run)

    assert metrics["completed_agents"] == 1
    assert metrics["agent_timings"]["Market Analyst"]["status"] == "completed"
    assert metrics["agent_timings"]["Market Analyst"]["duration_seconds"] >= 0
