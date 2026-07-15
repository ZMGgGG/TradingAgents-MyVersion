# TradingAgents/graph/trading_graph.py

import logging
import copy
import os
from pathlib import Path
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client
from tradingagents.backtesting.engine import BacktestResult, BacktestScenario, BatchBacktester
from tradingagents.core.data_snapshot import DataSnapshot

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import route_to_vendor

# Import the new abstract tool methods from agent_utils
from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_crypto_market_snapshot,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news
)

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=None,
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = (
            copy.deepcopy(config)
            if config is not None
            else copy.deepcopy(DEFAULT_CONFIG)
        )
        self.callbacks = callbacks or []
        selected_analysts = selected_analysts or ["market", "social", "news", "fundamentals"]

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
        self.role_llms = self._create_role_llms(llm_kwargs)
        
        self.memory_log = TradingMemoryLog(self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            analyst_concurrency_limit=self.config.get("analyst_concurrency_limit", 1),
            role_llms=self.role_llms,
        )

        self.propagator = Propagator(
            max_recur_limit=self.config.get("max_recur_limit", 100),
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)
        self.backtester = BatchBacktester(self)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph: keep the workflow for recompilation with a checkpointer.
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()
        timeout = self.config.get("timeout")
        max_retries = self.config.get("max_retries")
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        api_key = self.config.get("api_key")
        if api_key:
            kwargs["api_key"] = api_key

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        return kwargs

    def _create_role_llms(self, llm_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Create optional role-specific LLMs.

        Empty role model config falls back in GraphSetup:
        analysis/debate -> quick_thinking_llm, decision -> deep_thinking_llm.
        """
        role_config = {
            "analysis": self.config.get("analysis_think_llm"),
            "debate": self.config.get("debate_think_llm"),
            "decision": self.config.get("decision_think_llm"),
        }
        role_llms: Dict[str, Any] = {}
        for role, model in role_config.items():
            model_name = str(model or "").strip()
            if not model_name:
                continue
            fallback = (
                self.config["deep_think_llm"]
                if role == "decision"
                else self.config["quick_think_llm"]
            )
            if model_name == fallback:
                continue
            client = create_llm_client(
                provider=self.config["llm_provider"],
                model=model_name,
                base_url=self.config.get("backend_url"),
                **llm_kwargs,
            )
            role_llms[role] = client.get_llm()
        return role_llms

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Crypto-native market context
                    get_crypto_market_snapshot,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def _resolve_benchmark(self, ticker: str) -> str:
        """Pick the benchmark ticker for alpha calculation against ``ticker``.

        ``config["benchmark_ticker"]`` overrides everything when set; otherwise
        the suffix map matches the ticker's exchange suffix (e.g. ``.T`` for
        Tokyo). US-listed tickers without a dotted suffix fall through to the
        empty-suffix entry (SPY by default). Unrecognised suffixes (including
        US tickers with dots like ``BRK.B``) also fall back to the empty-suffix
        entry, which is the right default because the alpha calculation works
        in USD.
        """
        explicit = self.config.get("benchmark_ticker")
        if explicit:
            return explicit
        benchmark_map = self.config.get("benchmark_map", {})
        ticker_upper = ticker.upper()
        if ticker_upper.endswith(("-USD", "-USDT", "-USDC")):
            return self.config.get("crypto_benchmark_ticker") or "BTC-USD"
        for suffix, benchmark in benchmark_map.items():
            if suffix and ticker_upper.endswith(suffix.upper()):
                return benchmark
        return benchmark_map.get("", "SPY")

    def _fetch_returns(
        self, ticker: str, trade_date: str, holding_days: int = 5,
        benchmark: str = "SPY",
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        """Fetch raw and alpha return for ticker over holding_days from trade_date.

        ``benchmark`` is the index used as the alpha baseline (resolved by the
        caller via ``_resolve_benchmark``). Returns ``(raw_return, alpha_return,
        actual_holding_days)`` or ``(None, None, None)`` if price data is
        unavailable (too recent, delisted, or network error).
        """
        try:
            start = datetime.strptime(trade_date, "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)  # buffer for weekends/holidays
            end_str = end.strftime("%Y-%m-%d")

            stock = self._load_price_history_for_returns(ticker, trade_date, end_str)

            if len(stock) < 2:
                return None, None, None

            bench = self._load_price_history_for_returns(benchmark, trade_date, end_str)

            if len(bench) < 2:
                actual_days = min(holding_days, len(stock) - 1)
                raw = float(
                    (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                    / stock["Close"].iloc[0]
                )
                logger.warning(
                    "Benchmark %s unavailable for %s on %s; falling back to raw return only",
                    benchmark,
                    ticker,
                    trade_date,
                )
                return raw, 0.0, actual_days

            actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                / stock["Close"].iloc[0]
            )
            bench_ret = float(
                (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
                / bench["Close"].iloc[0]
            )
            alpha = raw - bench_ret
            return raw, alpha, actual_days
        except Exception as e:
            logger.warning(
                "Could not resolve outcome for %s on %s vs %s (will retry next run): %s",
                ticker, trade_date, benchmark, e,
            )
            return None, None, None

    def _load_price_history_for_returns(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Load post-analysis price history via the same vendor-compat path used elsewhere."""
        payload = route_to_vendor("get_stock_data", symbol, start_date, end_date)
        df = self._parse_price_payload_to_dataframe(payload)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return yf.Ticker(symbol).history(start=start_date, end=end_date)

    def _parse_price_payload_to_dataframe(self, payload: Any) -> pd.DataFrame:
        """Parse a vendor text payload into a normalized OHLCV DataFrame."""
        if not isinstance(payload, str):
            return pd.DataFrame()
        lines = payload.splitlines()
        csv_lines = [line for line in lines if line and not line.startswith("#")]
        if not csv_lines:
            return pd.DataFrame()
        try:
            from io import StringIO

            df = pd.read_csv(StringIO("\n".join(csv_lines)))
        except Exception:
            return pd.DataFrame()

        if "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
        df = df.set_index("Date")
        if "Close" in df.columns:
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            df = df.dropna(subset=["Close"])
        return df

    def _resolve_pending_entries(self, ticker: str) -> None:
        """Resolve pending log entries for ticker at the start of a new run.

        Fetches returns for each same-ticker pending entry, generates reflections,
        then writes all updates in a single atomic batch write to avoid redundant I/O.
        Skips entries whose price data is not yet available (too recent or delisted).

        Trade-off: only same-ticker entries are resolved per run.  Entries for
        other tickers accumulate until that ticker is run again.
        """
        pending = [e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker]
        if not pending:
            return

        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker, entry["date"], benchmark=benchmark,
            )
            if raw is None:
                continue  # price not available yet — try again next run
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
                benchmark_name=benchmark,
            )
            updates.append({
                "ticker": ticker,
                "trade_date": entry["date"],
                "raw_return": raw,
                "alpha_return": alpha,
                "holding_days": days,
                "reflection": reflection,
            })

        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def propagate(self, company_name, trade_date, asset_type: str = "stock"):
        """Run the trading agents graph for a company on a specific date.

        ``asset_type`` selects between the stock pipeline (default) and the
        crypto pipeline (``"crypto"``) shipped in #567 — the CLI auto-detects
        from the ticker; programmatic callers pass it explicitly. When
        ``checkpoint_enabled`` is set in config, the graph is recompiled with
        a per-ticker SqliteSaver so a crashed run can resume from the last
        successful node on a subsequent invocation with the same ticker+date.
        """
        self.ticker = company_name
        set_config({"_current_ticker": company_name})

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
            if step is not None:
                logger.info(
                    "Resuming from step %d for %s on %s", step, company_name, trade_date
                )
            else:
                logger.info("Starting fresh for %s on %s", company_name, trade_date)

        try:
            return self._run_graph(company_name, trade_date, asset_type=asset_type)
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        """Execute the graph and write the resulting state to disk and memory log."""
        # Initialize state — inject memory log context for PM.
        past_context = self.memory_log.get_past_context(company_name)
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, asset_type=asset_type, past_context=past_context
        )
        args = self.propagator.get_graph_args()

        # Inject thread_id so same ticker+date resumes, different date starts fresh.
        if self.config.get("checkpoint_enabled"):
            tid = thread_id(company_name, str(trade_date))
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = tid

        if self.debug:
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)
            # Streamed chunks are per-node deltas. Merge them so the returned
            # state matches what graph.invoke() yields in the non-debug path.
            final_state = {}
            for chunk in trace:
                final_state.update(chunk)
        else:
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection.
        self.curr_state = final_state
        final_state.setdefault("time_context", init_agent_state.get("time_context", {}))
        final_state["data_snapshot"] = DataSnapshot.from_state(final_state).to_log_payload()

        # Log state to disk.
        self._log_state(trade_date, final_state)

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear checkpoint on successful completion to avoid stale state.
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )

        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "asset_type": final_state.get("asset_type", "stock"),
            "trade_date": final_state["trade_date"],
            "time_context": final_state.get("time_context", {}),
            "data_snapshot": final_state.get("data_snapshot", {}),
            "market_report": final_state["market_report"],
            "market_features": final_state.get("market_features", {}),
            "market_evidence_ledger": final_state.get("market_evidence_ledger", {}),
            "sentiment_report": final_state["sentiment_report"],
            "sentiment_features": final_state.get("sentiment_features", {}),
            "sentiment_evidence_ledger": final_state.get("sentiment_evidence_ledger", {}),
            "news_report": final_state["news_report"],
            "news_features": final_state.get("news_features", {}),
            "news_evidence_ledger": final_state.get("news_evidence_ledger", {}),
            "fundamentals_report": final_state["fundamentals_report"],
            "fundamentals_features": final_state.get("fundamentals_features", {}),
            "fundamentals_evidence_ledger": final_state.get("fundamentals_evidence_ledger", {}),
            "alpha_mining_result": final_state.get("alpha_mining_result", {}),
            "alpha_experience_summary": final_state.get("alpha_experience_summary", {}),
            "factor_score": final_state.get("factor_score", {}),
            "position_sizing": final_state.get("position_sizing", {}),
            "risk_gate_result": final_state.get("risk_gate_result", {}),
            "execution_plan": final_state.get("execution_plan", {}),
            "run_metrics": final_state.get("run_metrics", {}),
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
                "bull_signal": final_state["investment_debate_state"].get("bull_signal", {}),
                "bear_signal": final_state["investment_debate_state"].get("bear_signal", {}),
                "signal_summary": final_state["investment_debate_state"].get("signal_summary", ""),
                "signal_score": final_state["investment_debate_state"].get("signal_score", 0.0),
                "signal_confidence": final_state["investment_debate_state"].get("signal_confidence", 0.0),
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
                "aggressive_signal": final_state["risk_debate_state"].get("aggressive_signal", {}),
                "conservative_signal": final_state["risk_debate_state"].get("conservative_signal", {}),
                "neutral_signal": final_state["risk_debate_state"].get("neutral_signal", {}),
                "signal_summary": final_state["risk_debate_state"].get("signal_summary", ""),
                "signal_score": final_state["risk_debate_state"].get("signal_score", 0.0),
                "signal_confidence": final_state["risk_debate_state"].get("signal_confidence", 0.0),
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file. Reject ticker values that would escape the
        # results directory when joined as a path component.
        safe_ticker = safe_ticker_component(self.ticker)
        directory = Path(self.config["results_dir"]) / safe_ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict[str(trade_date)], f, indent=4)

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)

    def run_batch_backtest(
        self,
        scenarios: List[BacktestScenario],
        holding_days: int = 5,
        initial_capital: float = 1.0,
    ) -> BacktestResult:
        """Run a baseline batch backtest over multiple scenarios."""
        return self.backtester.run(
            scenarios,
            holding_days=holding_days,
            initial_capital=initial_capital,
        )

    def run_backtest_from_final_states(
        self,
        scenarios: List[BacktestScenario],
        final_states: List[dict[str, Any]],
        holding_days: int = 5,
        initial_capital: float = 1.0,
    ) -> BacktestResult:
        """Backtest already-computed analysis results without re-running the graph."""
        return self.backtester.run_from_final_states(
            scenarios,
            final_states,
            holding_days=holding_days,
            initial_capital=initial_capital,
        )
