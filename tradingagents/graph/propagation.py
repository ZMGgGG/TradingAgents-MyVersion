# TradingAgents/graph/propagation.py

from typing import Dict, Any, List, Optional
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.core.time_context import TimeContext


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit
        self.default_timezone = "America/New_York"
        self.default_market_session = "close"

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        asset_type: str = "stock",
        past_context: str = "",
        analysis_lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "asset_type": asset_type,
            "trade_date": str(trade_date),
            "past_context": past_context,
            "time_context": TimeContext.from_trade_date(
                str(trade_date),
                timezone_name=self.default_timezone,
                market_session=self.default_market_session,
                analysis_lookback_days=analysis_lookback_days,
            ).model_dump(),
            "data_snapshot": {},
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                    "bull_signal": {},
                    "bear_signal": {},
                    "signal_summary": "",
                    "signal_score": 0.0,
                    "signal_confidence": 0.0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                    "aggressive_signal": {},
                    "conservative_signal": {},
                    "neutral_signal": {},
                    "signal_summary": "",
                    "signal_score": 0.0,
                    "signal_confidence": 0.0,
                }
            ),
            "market_report": "",
            "market_features": {},
            "market_evidence_ledger": {},
            "fundamentals_report": "",
            "fundamentals_features": {},
            "sentiment_report": "",
            "sentiment_features": {},
            "sentiment_evidence_ledger": {},
            "news_report": "",
            "news_features": {},
            "news_evidence_ledger": {},
            "alpha_mining_result": {},
            "alpha_experience_summary": {},
            "fundamentals_evidence_ledger": {},
            "factor_score": {},
            "position_sizing": {},
            "risk_gate_result": {},
            "execution_plan": {},
        }

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }
