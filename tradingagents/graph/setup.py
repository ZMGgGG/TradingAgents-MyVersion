# TradingAgents/graph/setup.py

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: Dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        analyst_concurrency_limit: int = 1,
        role_llms: Dict[str, Any] | None = None,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.analyst_concurrency_limit = analyst_concurrency_limit
        self.role_llms = role_llms or {}

    def _role_llm(self, role: str, fallback: Any) -> Any:
        return self.role_llms.get(role) or fallback

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        plan = build_analyst_execution_plan(
            selected_analysts,
            concurrency_limit=self.analyst_concurrency_limit,
        )

        analysis_llm = self._role_llm("analysis", self.quick_thinking_llm)
        debate_llm = self._role_llm("debate", self.quick_thinking_llm)
        decision_llm = self._role_llm("decision", self.deep_thinking_llm)

        analyst_factories = {
            "market": lambda: create_market_analyst(analysis_llm),
            "social": lambda: create_sentiment_analyst(analysis_llm),
            "news": lambda: create_news_analyst(analysis_llm),
            "fundamentals": lambda: create_fundamentals_analyst(analysis_llm),
        }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(debate_llm)
        bear_researcher_node = create_bear_researcher(debate_llm)
        research_manager_node = create_research_manager(decision_llm)
        factor_manager_node = create_factor_manager()
        trader_node = create_trader(debate_llm)
        position_manager_node = create_position_manager()
        risk_gate_manager_node = create_risk_gate_manager()

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(debate_llm)
        neutral_analyst = create_neutral_debator(debate_llm)
        conservative_analyst = create_conservative_debator(debate_llm)
        portfolio_manager_node = create_portfolio_manager(decision_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        parallel_analysts = self.analyst_concurrency_limit > 1
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete(remove_existing=not parallel_analysts))
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Factor Manager", factor_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Position Manager", position_manager_node)
        workflow.add_node("Risk Gate", risk_gate_manager_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # Define analyst edges. With concurrency > 1, all selected analysts
        # start together and the graph waits for every clear node before the
        # research debate begins. Concurrency == 1 preserves the legacy chain.
        if parallel_analysts:
            for spec in plan.specs:
                workflow.add_edge(START, spec.agent_node)
        else:
            workflow.add_edge(START, plan.specs[0].agent_node)

        for i, spec in enumerate(plan.specs):
            current_analyst = spec.agent_node
            current_tools = spec.tool_node
            current_clear = spec.clear_node

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            if parallel_analysts:
                continue
            if i < len(plan.specs) - 1:
                workflow.add_edge(current_clear, plan.specs[i + 1].agent_node)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        if parallel_analysts:
            workflow.add_edge([spec.clear_node for spec in plan.specs], "Bull Researcher")

        # Add remaining edges
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Factor Manager")
        workflow.add_edge("Factor Manager", "Trader")
        workflow.add_edge("Trader", "Position Manager")
        workflow.add_edge("Position Manager", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Risk Gate": "Risk Gate",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Risk Gate": "Risk Gate",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Risk Gate": "Risk Gate",
            },
        )
        workflow.add_edge("Risk Gate", "Portfolio Manager")

        workflow.add_edge("Portfolio Manager", END)

        return workflow
