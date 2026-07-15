from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_provider_kwargs_forward_timeout_and_retries():
    graph = object.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "qwen-cn",
        "timeout": 90,
        "max_retries": 2,
    }

    kwargs = graph._get_provider_kwargs()

    assert kwargs["timeout"] == 90
    assert kwargs["max_retries"] == 2


def test_provider_kwargs_preserve_provider_specific_options():
    graph = object.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "openai",
        "timeout": 120,
        "max_retries": 1,
        "openai_reasoning_effort": "medium",
    }

    kwargs = graph._get_provider_kwargs()

    assert kwargs["timeout"] == 120
    assert kwargs["max_retries"] == 1
    assert kwargs["reasoning_effort"] == "medium"


def test_provider_kwargs_forward_explicit_api_key():
    graph = object.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "qwen-cn",
        "api_key": "sk-task-local",
    }

    kwargs = graph._get_provider_kwargs()

    assert kwargs["api_key"] == "sk-task-local"
