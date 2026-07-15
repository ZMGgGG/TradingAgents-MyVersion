from typing import Optional
import datetime
import json
import typer
import questionary
from pathlib import Path
from functools import wraps
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live
from rich.columns import Columns
from rich.markdown import Markdown
from rich.layout import Layout
from rich.text import Text
from rich.table import Table
from collections import deque
import time
from rich.tree import Tree
from rich import box
from rich.align import Align
from rich.rule import Rule

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.graph.analyst_execution import (
    AnalystWallTimeTracker,
    build_analyst_execution_plan,
    get_initial_analyst_node,
    sync_analyst_tracker_from_chunk,
)
from tradingagents.core.data_snapshot import DataSnapshot
from tradingagents.alpha_mining import (
    AlphaEvaluator,
    AlphaMiningEpisode,
    AlphaMiningHistory,
    AlphaRegistry,
    AlphaRegistryEntry,
    QuantaAlphaMiner,
    AlphaCandidate,
    alpha_text,
    build_alpha_experience_summary,
    generate_crossover_set,
    generate_mutation_set,
)
from tradingagents.backtesting import BacktestScenario
from tradingagents.backtesting.engine import BatchBacktester
from tradingagents.decisioning.execution_policy import candidate_signal_to_execution
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.evaluation import (
    ReportEvaluator,
    extract_reference_text_from_html_file,
    extract_reference_text_from_pdf_file,
    render_report_evaluation,
)
from tradingagents.graph.checkpointer import clear_all_checkpoints
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.dataflows.interface import route_to_vendor
from cli.models import AnalystType
from cli.utils import *
from cli.announcements import fetch_announcements, display_announcements
from cli.stats_handler import StatsCallbackHandler
from cli.report_io import (
    append_backtest_summary_to_report,
    append_report_evaluation_to_report,
    save_report_to_disk,
)
from cli.report_helpers import build_evidence_ledger_sections, build_structured_summary_status
from cli.alpha_flow import (
    choose_alpha_source,
    discover_alpha_sources,
    print_alpha_mining_success,
    run_alpha_mining_for_source,
)
from cli.backtest_flow import (
    display_backtest_result,
    display_backtest_summary,
    parse_holding_days_input,
    parse_initial_capital_input,
    save_backtest_result_to_disk,
    save_backtest_summary_to_disk,
)

console = Console()

app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: Multi-Agents LLM Financial Trading Framework",
    add_completion=True,  # Enable shell completion
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    checkpoint: bool = typer.Option(
        False,
        "--checkpoint",
        help="Enable checkpoint/resume: save state after each node so a crashed run can resume.",
    ),
    clear_checkpoints: bool = typer.Option(
        False,
        "--clear-checkpoints",
        help="Delete all saved checkpoints before running (force fresh start).",
    ),
):
    """Default to analysis when no explicit subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    if clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints
        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        console.print(f"[yellow]Cleared {n} checkpoint(s).[/yellow]")
    run_analysis(checkpoint=checkpoint)


# Create a deque to store recent messages with a maximum length
class MessageBuffer:
    # Fixed teams that always run (not user-selectable)
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    # Analyst name mapping
    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Sentiment Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }

    # Report section mapping: section -> (analyst_key for filtering, finalizing_agent)
    # analyst_key: which analyst selection controls this section (None = always included)
    # finalizing_agent: which agent must be "completed" for this report to count as done
    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Sentiment Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    def __init__(self, max_length=100):
        self.messages = deque(maxlen=max_length)
        self.tool_calls = deque(maxlen=max_length)
        self.current_report = None
        self.final_report = None  # Store the complete final report
        self.agent_status = {}
        self.current_agent = None
        self.report_sections = {}
        self.selected_analysts = []
        self._processed_message_ids = set()

    def init_for_analysis(self, selected_analysts):
        """Initialize agent status and report sections based on selected analysts.

        Args:
            selected_analysts: List of analyst type strings (e.g., ["market", "news"])
        """
        self.selected_analysts = [a.lower() for a in selected_analysts]

        # Build agent_status dynamically
        self.agent_status = {}

        # Add selected analysts
        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"

        # Add fixed teams
        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        # Build report_sections dynamically
        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = None

        # Reset other state
        self.current_report = None
        self.final_report = None
        self.current_agent = None
        self.messages.clear()
        self.tool_calls.clear()
        self._processed_message_ids.clear()

    def get_completed_reports_count(self):
        """Count reports that are finalized (their finalizing agent is completed).

        A report is considered complete when:
        1. The report section has content (not None), AND
        2. The agent responsible for finalizing that report has status "completed"

        This prevents interim updates (like debate rounds) from counting as completed.
        """
        count = 0
        for section in self.report_sections:
            if section not in self.REPORT_SECTIONS:
                continue
            _, finalizing_agent = self.REPORT_SECTIONS[section]
            # Report is complete if it has content AND its finalizing agent is done
            has_content = self.report_sections.get(section) is not None
            agent_done = self.agent_status.get(finalizing_agent) == "completed"
            if has_content and agent_done:
                count += 1
        return count

    def add_message(self, message_type, content):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.append((timestamp, message_type, content))

    def add_tool_call(self, tool_name, args):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.tool_calls.append((timestamp, tool_name, args))

    def update_agent_status(self, agent, status):
        if agent in self.agent_status:
            self.agent_status[agent] = status
            self.current_agent = agent

    def update_report_section(self, section_name, content):
        if section_name in self.report_sections:
            self.report_sections[section_name] = content
            self._update_current_report()

    def _update_current_report(self):
        # For the panel display, only show the most recently updated section
        latest_section = None
        latest_content = None

        # Find the most recently updated section
        for section, content in self.report_sections.items():
            if content is not None:
                latest_section = section
                latest_content = content
               
        if latest_section and latest_content:
            # Format the current section for display
            section_titles = {
                "market_report": "Market Analysis",
                "sentiment_report": "Social Sentiment",
                "news_report": "News Analysis",
                "fundamentals_report": "Fundamentals Analysis",
                "investment_plan": "Research Team Decision",
                "trader_investment_plan": "Trading Team Plan",
                "final_trade_decision": "Portfolio Management Decision",
            }
            self.current_report = (
                f"### {section_titles[latest_section]}\n{latest_content}"
            )

        # Update the final complete report
        self._update_final_report()

    def _update_final_report(self):
        report_parts = []

        # Analyst Team Reports - use .get() to handle missing sections
        analyst_sections = ["market_report", "sentiment_report", "news_report", "fundamentals_report"]
        if any(self.report_sections.get(section) for section in analyst_sections):
            report_parts.append("## Analyst Team Reports")
            if self.report_sections.get("market_report"):
                report_parts.append(
                    f"### Market Analysis\n{self.report_sections['market_report']}"
                )
            if self.report_sections.get("sentiment_report"):
                report_parts.append(
                    f"### Social Sentiment\n{self.report_sections['sentiment_report']}"
                )
            if self.report_sections.get("news_report"):
                report_parts.append(
                    f"### News Analysis\n{self.report_sections['news_report']}"
                )
            if self.report_sections.get("fundamentals_report"):
                report_parts.append(
                    f"### Fundamentals Analysis\n{self.report_sections['fundamentals_report']}"
                )

        # Research Team Reports
        if self.report_sections.get("investment_plan"):
            report_parts.append("## Research Team Decision")
            report_parts.append(f"{self.report_sections['investment_plan']}")

        # Trading Team Reports
        if self.report_sections.get("trader_investment_plan"):
            report_parts.append("## Trading Team Plan")
            report_parts.append(f"{self.report_sections['trader_investment_plan']}")

        # Portfolio Management Decision
        if self.report_sections.get("final_trade_decision"):
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(f"{self.report_sections['final_trade_decision']}")

        self.final_report = "\n\n".join(report_parts) if report_parts else None


message_buffer = MessageBuffer()


def create_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_column(
        Layout(name="upper", ratio=3), Layout(name="analysis", ratio=5)
    )
    layout["upper"].split_row(
        Layout(name="progress", ratio=2), Layout(name="messages", ratio=3)
    )
    return layout


def format_tokens(n):
    """Format token count for display."""
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def update_display(layout, spinner_text=None, stats_handler=None, start_time=None):
    # Header with welcome message
    layout["header"].update(
        Panel(
            "[bold green]Welcome to TradingAgents CLI[/bold green]\n"
            "[dim]© [Tauric Research](https://github.com/TauricResearch)[/dim]",
            title="Welcome to TradingAgents",
            border_style="green",
            padding=(1, 2),
            expand=True,
        )
    )

    # Progress panel showing agent status
    progress_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        box=box.SIMPLE_HEAD,  # Use simple header with horizontal lines
        title=None,  # Remove the redundant Progress title
        padding=(0, 2),  # Add horizontal padding
        expand=True,  # Make table expand to fill available space
    )
    progress_table.add_column("Team", style="cyan", justify="center", width=20)
    progress_table.add_column("Agent", style="green", justify="center", width=20)
    progress_table.add_column("Status", style="yellow", justify="center", width=20)

    # Group agents by team - filter to only include agents in agent_status
    all_teams = {
        "Analyst Team": [
            "Market Analyst",
            "Sentiment Analyst",
            "News Analyst",
            "Fundamentals Analyst",
        ],
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    # Filter teams to only include agents that are in agent_status
    teams = {}
    for team, agents in all_teams.items():
        active_agents = [a for a in agents if a in message_buffer.agent_status]
        if active_agents:
            teams[team] = active_agents

    for team, agents in teams.items():
        # Add first agent with team name
        first_agent = agents[0]
        status = message_buffer.agent_status.get(first_agent, "pending")
        if status == "in_progress":
            spinner = Spinner(
                "dots", text="[blue]in_progress[/blue]", style="bold cyan"
            )
            status_cell = spinner
        else:
            status_color = {
                "pending": "yellow",
                "completed": "green",
                "error": "red",
            }.get(status, "white")
            status_cell = f"[{status_color}]{status}[/{status_color}]"
        progress_table.add_row(team, first_agent, status_cell)

        # Add remaining agents in team
        for agent in agents[1:]:
            status = message_buffer.agent_status.get(agent, "pending")
            if status == "in_progress":
                spinner = Spinner(
                    "dots", text="[blue]in_progress[/blue]", style="bold cyan"
                )
                status_cell = spinner
            else:
                status_color = {
                    "pending": "yellow",
                    "completed": "green",
                    "error": "red",
                }.get(status, "white")
                status_cell = f"[{status_color}]{status}[/{status_color}]"
            progress_table.add_row("", agent, status_cell)

        # Add horizontal line after each team
        progress_table.add_row("─" * 20, "─" * 20, "─" * 20, style="dim")

    layout["progress"].update(
        Panel(progress_table, title="Progress", border_style="cyan", padding=(1, 2))
    )

    # Messages panel showing recent messages and tool calls
    messages_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        expand=True,  # Make table expand to fill available space
        box=box.MINIMAL,  # Use minimal box style for a lighter look
        show_lines=True,  # Keep horizontal lines
        padding=(0, 1),  # Add some padding between columns
    )
    messages_table.add_column("Time", style="cyan", width=8, justify="center")
    messages_table.add_column("Type", style="green", width=10, justify="center")
    messages_table.add_column(
        "Content", style="white", no_wrap=False, ratio=1
    )  # Make content column expand

    # Combine tool calls and messages
    all_messages = []

    # Add tool calls
    for timestamp, tool_name, args in message_buffer.tool_calls:
        formatted_args = format_tool_args(args)
        all_messages.append((timestamp, "Tool", f"{tool_name}: {formatted_args}"))

    # Add regular messages
    for timestamp, msg_type, content in message_buffer.messages:
        content_str = str(content) if content else ""
        if len(content_str) > 200:
            content_str = content_str[:197] + "..."
        all_messages.append((timestamp, msg_type, content_str))

    # Sort by timestamp descending (newest first)
    all_messages.sort(key=lambda x: x[0], reverse=True)

    # Calculate how many messages we can show based on available space
    max_messages = 12

    # Get the first N messages (newest ones)
    recent_messages = all_messages[:max_messages]

    # Add messages to table (already in newest-first order)
    for timestamp, msg_type, content in recent_messages:
        # Format content with word wrapping
        wrapped_content = Text(content, overflow="fold")
        messages_table.add_row(timestamp, msg_type, wrapped_content)

    layout["messages"].update(
        Panel(
            messages_table,
            title="Messages & Tools",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # Analysis panel showing current report
    if message_buffer.current_report:
        layout["analysis"].update(
            Panel(
                Markdown(message_buffer.current_report),
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        layout["analysis"].update(
            Panel(
                "[italic]Waiting for analysis report...[/italic]",
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )

    # Footer with statistics
    # Agent progress - derived from agent_status dict
    agents_completed = sum(
        1 for status in message_buffer.agent_status.values() if status == "completed"
    )
    agents_total = len(message_buffer.agent_status)

    # Report progress - based on agent completion (not just content existence)
    reports_completed = message_buffer.get_completed_reports_count()
    reports_total = len(message_buffer.report_sections)

    # Build stats parts
    stats_parts = [f"Agents: {agents_completed}/{agents_total}"]

    # LLM and tool stats from callback handler
    if stats_handler:
        stats = stats_handler.get_stats()
        stats_parts.append(f"LLM: {stats['llm_calls']}")
        stats_parts.append(f"Tools: {stats['tool_calls']}")

        # Token display with graceful fallback
        if stats["tokens_in"] > 0 or stats["tokens_out"] > 0:
            tokens_str = f"Tokens: {format_tokens(stats['tokens_in'])}\u2191 {format_tokens(stats['tokens_out'])}\u2193"
        else:
            tokens_str = "Tokens: --"
        stats_parts.append(tokens_str)

    stats_parts.append(f"Reports: {reports_completed}/{reports_total}")

    # Elapsed time
    if start_time:
        elapsed = time.time() - start_time
        elapsed_str = f"\u23f1 {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        stats_parts.append(elapsed_str)

    stats_table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    stats_table.add_column("Stats", justify="center")
    stats_table.add_row(" | ".join(stats_parts))

    layout["footer"].update(Panel(stats_table, border_style="grey50"))


def get_user_selections():
    """Get all user selections before starting the analysis display."""
    # Display ASCII art welcome message
    with open(Path(__file__).parent / "static" / "welcome.txt", "r", encoding="utf-8") as f:
        welcome_ascii = f.read()

    # Create welcome box content
    welcome_content = f"{welcome_ascii}\n"
    welcome_content += "[bold green]TradingAgents: Multi-Agents LLM Financial Trading Framework - CLI[/bold green]\n\n"
    welcome_content += "[bold]Workflow Steps:[/bold]\n"
    welcome_content += "I. Analyst Team → II. Research Team → III. Trader → IV. Risk Management → V. Portfolio Management\n\n"
    welcome_content += (
        "[dim]Built by [Tauric Research](https://github.com/TauricResearch)[/dim]"
    )

    # Create and center the welcome box
    welcome_box = Panel(
        welcome_content,
        border_style="green",
        padding=(1, 2),
        title="Welcome to TradingAgents",
        subtitle="Multi-Agents LLM Financial Trading Framework",
    )
    console.print(Align.center(welcome_box))
    console.print()
    console.print()  # Add vertical space before announcements

    # Fetch and display announcements (silent on failure)
    announcements = fetch_announcements()
    display_announcements(console, announcements)

    # Create a boxed questionnaire for each step
    def create_question_box(title, prompt, default=None):
        box_content = f"[bold]{title}[/bold]\n"
        box_content += f"[dim]{prompt}[/dim]"
        if default:
            box_content += f"\n[dim]Default: {default}[/dim]"
        return Panel(box_content, border_style="blue", padding=(1, 2))

    # Step 1: Ticker symbol
    console.print(
        create_question_box(
            "Step 1: Ticker Symbol",
            "Enter the exact ticker symbol to analyze, including exchange suffix when needed (examples: SPY, CNC.TO, 7203.T, 0700.HK)",
            "SPY",
        )
    )
    selected_ticker = get_ticker()
    asset_type = detect_asset_type(selected_ticker)
    console.print(
        f"[green]Detected asset type:[/green] {asset_type.value}"
    )

    # Step 2: Analysis date
    default_date = datetime.datetime.now().strftime("%Y-%m-%d")
    console.print(
        create_question_box(
            "Step 2: Analysis Date",
            "Enter the analysis date (YYYY-MM-DD)",
            default_date,
        )
    )
    analysis_date = get_analysis_date()

    # Step 3: Shared analysis lookback window
    console.print(
        create_question_box(
            "Step 3: Shared Lookback Window",
            "Select one lookback window to reuse across market, news, and sentiment analysis",
            "30 days",
        )
    )
    analysis_lookback_days = select_analysis_lookback_days()

    # Step 4: Output language
    console.print(
        create_question_box(
            "Step 4: Output Language",
            "Select the language for analyst reports and final decision"
        )
    )
    output_language = ask_output_language()

    # Step 5: Select analysts
    console.print(
        create_question_box(
            "Step 5: Analysts Team", "Select your LLM analyst agents for the analysis"
        )
    )
    selected_analysts = select_analysts(asset_type)
    console.print(
        f"[green]Selected analysts:[/green] {', '.join(analyst.value for analyst in selected_analysts)}"
    )

    # Step 6: Research depth
    console.print(
        create_question_box(
            "Step 6: Research Depth", "Select your research depth level"
        )
    )
    selected_research_depth = select_research_depth()

    # Step 7: LLM Provider
    console.print(
        create_question_box(
            "Step 7: LLM Provider", "Select your LLM provider"
        )
    )
    selected_llm_provider, backend_url = select_llm_provider()

    # Providers with regional endpoints prompt for the region as a secondary
    # step so the main dropdown stays clean (mainland China and international
    # accounts cannot share API keys).
    if selected_llm_provider == "qwen":
        selected_llm_provider, backend_url = ask_qwen_region()
    elif selected_llm_provider == "minimax":
        selected_llm_provider, backend_url = ask_minimax_region()
    elif selected_llm_provider == "glm":
        selected_llm_provider, backend_url = ask_glm_region()

    # For Ollama, surface the resolved endpoint (OLLAMA_BASE_URL vs default)
    # before model selection so it's obvious where we're connecting.
    if selected_llm_provider == "ollama":
        confirm_ollama_endpoint(backend_url)

    # Confirm the provider's API key is present; prompt the user to paste
    # one and persist it to .env if it's missing, so the analysis run
    # doesn't fail later at the first API call.
    ensure_api_key(selected_llm_provider)

    # Step 8: Thinking agents
    console.print(
        create_question_box(
            "Step 8: Thinking Agents", "Select your thinking agents for analysis"
        )
    )
    selected_shallow_thinker = select_shallow_thinking_agent(selected_llm_provider)
    selected_deep_thinker = select_deep_thinking_agent(selected_llm_provider)

    # Step 9: Provider-specific thinking configuration
    thinking_level = None
    reasoning_effort = None
    anthropic_effort = None

    provider_lower = selected_llm_provider.lower()
    if provider_lower == "google":
        console.print(
            create_question_box(
                "Step 9: Thinking Mode",
                "Configure Gemini thinking mode"
            )
        )
        thinking_level = ask_gemini_thinking_config()
    elif provider_lower == "openai":
        console.print(
            create_question_box(
                "Step 9: Reasoning Effort",
                "Configure OpenAI reasoning effort level"
            )
        )
        reasoning_effort = ask_openai_reasoning_effort()
    elif provider_lower == "anthropic":
        console.print(
            create_question_box(
                "Step 9: Effort Level",
                "Configure Claude effort level"
            )
        )
        anthropic_effort = ask_anthropic_effort()

    return {
        "ticker": selected_ticker,
        "asset_type": asset_type.value,
        "analysis_date": analysis_date,
        "analysis_lookback_days": analysis_lookback_days,
        "analysts": selected_analysts,
        "research_depth": selected_research_depth,
        "llm_provider": selected_llm_provider.lower(),
        "backend_url": backend_url,
        "shallow_thinker": selected_shallow_thinker,
        "deep_thinker": selected_deep_thinker,
        "google_thinking_level": thinking_level,
        "openai_reasoning_effort": reasoning_effort,
        "anthropic_effort": anthropic_effort,
        "output_language": output_language,
    }


def get_ticker():
    """Get ticker symbol from user input, preserving exchange suffixes."""
    # typer.prompt strips trailing dot-suffixes on some shells (e.g. 000404.SH
    # collapses to 000404). questionary.text reads the raw line.
    ticker = questionary.text(
        "",
        validate=lambda value: (
            not value.strip()
            or (
                all(ch.isalnum() or ch in "._-^" for ch in value.strip())
                and len(value.strip()) <= 32
            )
        )
        or "Please enter a valid ticker symbol, e.g. AAPL, 000404.SZ, 0700.HK.",
    ).ask()

    if ticker is None:
        console.print("\n[red]No ticker symbol provided. Exiting...[/red]")
        raise typer.Exit(1)

    return (ticker.strip() or "SPY").upper()


def get_analysis_date():
    """Get the analysis date from user input."""
    while True:
        date_str = typer.prompt(
            "", default=datetime.datetime.now().strftime("%Y-%m-%d")
        )
        try:
            # Validate date format and ensure it's not in the future
            analysis_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if analysis_date.date() > datetime.datetime.now().date():
                console.print("[red]Error: Analysis date cannot be in the future[/red]")
                continue
            return date_str
        except ValueError:
            console.print(
                "[red]Error: Invalid date format. Please use YYYY-MM-DD[/red]"
            )


def display_report_evaluation(evaluation):
    """Display report quality evaluation against a reference answer."""
    console.print()
    console.print(Rule("Research Report Evaluation", style="bold cyan"))

    score_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    score_table.add_column("Dimension", style="cyan")
    score_table.add_column("Score", style="green")
    score_table.add_row("Factual Coverage", f"{evaluation.factual_coverage:.1f}/10")
    score_table.add_row("Evidence Support", f"{evaluation.evidence_support:.1f}/10")
    score_table.add_row("Reasoning Consistency", f"{evaluation.reasoning_consistency:.1f}/10")
    score_table.add_row("Risk Awareness", f"{evaluation.risk_awareness:.1f}/10")
    score_table.add_row("Actionability", f"{evaluation.actionability:.1f}/10")
    score_table.add_row("Writing Quality", f"{evaluation.writing_quality:.1f}/10")
    score_table.add_row("Total", f"{evaluation.total_score:.1f}/100")
    console.print(Panel(score_table, title="Scorecard", border_style="cyan"))

    critique = "\n\n".join(
        [
            f"**Verdict**\n{evaluation.verdict}",
            f"**Missing Points**\n{evaluation.missing_points}",
            f"**Unsupported Claims**\n{evaluation.unsupported_claims}",
            f"**Correction Plan**\n{evaluation.correction_plan}",
            f"**Prompt Tuning Notes**\n{evaluation.prompt_tuning_notes}",
        ]
    )
    console.print(Panel(Markdown(critique), title="Correction Notes", border_style="cyan", padding=(1, 2)))


def save_report_evaluation_to_disk(evaluation, save_path: Path):
    """Save report evaluation markdown under the report directory."""
    evaluation_dir = save_path / "7_evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    file_path = evaluation_dir / "report_evaluation.md"
    file_path.write_text(render_report_evaluation(evaluation), encoding="utf-8")
    return file_path


def load_reference_text(reference_path: Path) -> str:
    """Load a local reference answer from markdown/text or saved HTML."""
    suffix = reference_path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return extract_reference_text_from_html_file(reference_path)
    if suffix == ".pdf":
        return extract_reference_text_from_pdf_file(reference_path)
    return reference_path.read_text(encoding="utf-8")


def discover_reference_reports(root: Path | None = None) -> list[Path]:
    """Find local reference reports under the default research directory."""
    base = (root or Path.cwd() / "研报").expanduser()
    if not base.exists():
        return []
    matches = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".html", ".htm", ".pdf"}:
            continue
        if "_files" in path.parts:
            continue
        matches.append(path)
    return matches




def choose_reference_report() -> str:
    """Select a reference report from `研报/` or enter a custom path."""
    candidates = discover_reference_reports()
    choices = [
        questionary.Choice(str(path.relative_to(Path.cwd())), value=str(path))
        for path in candidates
    ]
    choices.append(questionary.Choice("Manual path entry", value="__manual__"))

    selected = questionary.select(
        "Select a reference report:",
        choices=choices,
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:cyan noinherit"),
                ("highlighted", "fg:cyan noinherit"),
                ("pointer", "fg:cyan noinherit"),
            ]
        ),
    ).ask()

    if selected == "__manual__":
        return typer.prompt(
            "Reference answer path (.md/.txt/.html/.pdf)",
            default="",
        ).strip()

    return selected or ""


def display_complete_report(final_state):
    """Display the complete analysis report sequentially (avoids truncation)."""
    console.print()
    console.print(Rule("Complete Analysis Report", style="bold green"))

    statuses = build_structured_summary_status(final_state)
    status_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    status_table.add_column("Agent", style="cyan")
    status_table.add_column("Summary Block", style="yellow")
    for agent, status in statuses:
        status_table.add_row(agent, status)
    console.print(Panel(status_table, title="Structured Summary Status", border_style="green"))

    # I. Analyst Team Reports
    analysts = []
    if final_state.get("market_report"):
        analysts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts.append(("Sentiment Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analysts:
        console.print(Panel("[bold]I. Analyst Team Reports[/bold]", border_style="cyan"))
        for title, content in analysts:
            console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

    # II. Research Team Reports
    if final_state.get("investment_debate_state"):
        debate = final_state["investment_debate_state"]
        research = []
        if debate.get("bull_history"):
            research.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research.append(("Research Manager", debate["judge_decision"]))
        if research:
            console.print(Panel("[bold]II. Research Team Decision[/bold]", border_style="magenta"))
            for title, content in research:
                console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

    # III. Trading Team
    if final_state.get("trader_investment_plan"):
        console.print(Panel("[bold]III. Trading Team Plan[/bold]", border_style="yellow"))
        console.print(Panel(Markdown(final_state["trader_investment_plan"]), title="Trader", border_style="blue", padding=(1, 2)))

    decisioning_items = []
    if final_state.get("alpha_mining_result"):
        decisioning_items.append(("QuantaAlpha Mining", final_state["alpha_mining_result"]))
    if final_state.get("factor_score"):
        decisioning_items.append(("Factor Score", final_state["factor_score"]))
    if final_state.get("position_sizing"):
        decisioning_items.append(("Position Sizing", final_state["position_sizing"]))
    if final_state.get("risk_gate_result"):
        decisioning_items.append(("Risk Gate", final_state["risk_gate_result"]))
    if final_state.get("execution_plan"):
        decisioning_items.append(("Execution Plan", final_state["execution_plan"]))
    if decisioning_items:
        console.print(Panel("[bold]III-B. Stage Two Decisioning[/bold]", border_style="cyan"))
        for title, payload in decisioning_items:
            console.print(
                Panel(
                    Markdown(f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"),
                    title=title,
                    border_style="blue",
                    padding=(1, 2),
                )
            )

    if final_state.get("alpha_experience_summary"):
        console.print(Panel("[bold]III-C. Alpha Experience Summary[/bold]", border_style="cyan"))
        alpha_summary = final_state["alpha_experience_summary"]
        alpha_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        alpha_table.add_column("Field", style="cyan")
        alpha_table.add_column("Value", style="green")
        alpha_table.add_row("Registry Entries", str(alpha_summary.get("registry_entry_count", 0)))
        alpha_table.add_row("History Episodes", str(alpha_summary.get("history_episode_count", 0)))
        alpha_table.add_row("Selected Alpha", str(alpha_summary.get("selected_alpha_name", "")))
        alpha_table.add_row("Selected Status", str(alpha_summary.get("selected_alpha_status", "")))
        alpha_table.add_row("Registry Reuse", str(alpha_summary.get("used_registry_experience", False)))
        alpha_table.add_row("Avg Realized Return", f"{alpha_summary.get('average_realized_return', 0.0):.2%}")
        alpha_table.add_row("Avg Realized Alpha", f"{alpha_summary.get('average_realized_alpha', 0.0):.2%}")
        alpha_table.add_row("Avg Eval Score", f"{alpha_summary.get('average_evaluation_score', 0.0):.4f}")
        alpha_table.add_row("Positive Alpha Win Rate", f"{alpha_summary.get('positive_alpha_win_rate', 0.0):.2%}")
        console.print(Panel(alpha_table, title="Alpha Summary", border_style="cyan"))
        console.print(
            Panel(
                Markdown(
                    f"```json\n{json.dumps(final_state['alpha_experience_summary'], ensure_ascii=False, indent=2)}\n```"
                ),
                title="Alpha Experience Summary",
                border_style="blue",
                padding=(1, 2),
            )
        )

    evidence_items = build_evidence_ledger_sections(final_state)
    if evidence_items:
        console.print(Panel("[bold]III-D. Evidence Ledgers[/bold]", border_style="cyan"))
        for title, payload in evidence_items:
            console.print(
                Panel(
                    Markdown(f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"),
                    title=title,
                    border_style="blue",
                    padding=(1, 2),
                )
            )

    # IV. Risk Management Team
    if final_state.get("risk_debate_state"):
        risk = final_state["risk_debate_state"]
        risk_reports = []
        if risk.get("aggressive_history"):
            risk_reports.append(("Aggressive Analyst", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_reports.append(("Conservative Analyst", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_reports.append(("Neutral Analyst", risk["neutral_history"]))
        if risk_reports:
            console.print(Panel("[bold]IV. Risk Management Team Decision[/bold]", border_style="red"))
            for title, content in risk_reports:
                console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

        # V. Portfolio Manager Decision
        if risk.get("judge_decision"):
            console.print(Panel("[bold]V. Portfolio Manager Decision[/bold]", border_style="green"))
            console.print(Panel(Markdown(risk["judge_decision"]), title="Portfolio Manager", border_style="blue", padding=(1, 2)))

    report_evaluation = final_state.get("report_evaluation")
    if report_evaluation:
        console.print(Panel("[bold]VI. Report Evaluation[/bold]", border_style="cyan"))
        score_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        score_table.add_column("Dimension", style="cyan")
        score_table.add_column("Score", style="green")
        score_table.add_row("Factual Coverage", f"{report_evaluation.get('factual_coverage', 0.0):.1f}/10")
        score_table.add_row("Evidence Support", f"{report_evaluation.get('evidence_support', 0.0):.1f}/10")
        score_table.add_row("Reasoning Consistency", f"{report_evaluation.get('reasoning_consistency', 0.0):.1f}/10")
        score_table.add_row("Risk Awareness", f"{report_evaluation.get('risk_awareness', 0.0):.1f}/10")
        score_table.add_row("Actionability", f"{report_evaluation.get('actionability', 0.0):.1f}/10")
        score_table.add_row("Writing Quality", f"{report_evaluation.get('writing_quality', 0.0):.1f}/10")
        score_table.add_row("Total", f"{report_evaluation.get('total_score', 0.0):.1f}/100")
        console.print(Panel(score_table, title="Scorecard", border_style="cyan"))

        critique = "\n\n".join(
            [
                f"**Verdict**\n{report_evaluation.get('verdict', '')}",
                f"**Missing Points**\n{report_evaluation.get('missing_points', '')}",
                f"**Unsupported Claims**\n{report_evaluation.get('unsupported_claims', '')}",
                f"**Correction Plan**\n{report_evaluation.get('correction_plan', '')}",
                f"**Prompt Tuning Notes**\n{report_evaluation.get('prompt_tuning_notes', '')}",
            ]
        )
        console.print(Panel(Markdown(critique), title="Correction Notes", border_style="cyan", padding=(1, 2)))


def update_research_team_status(status):
    """Update status for research team members (not Trader)."""
    research_team = ["Bull Researcher", "Bear Researcher", "Research Manager"]
    for agent in research_team:
        message_buffer.update_agent_status(agent, status)


# Ordered list of analysts for status transitions
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


def update_analyst_statuses(message_buffer, chunk, wall_time_tracker=None):
    """Update analyst statuses based on accumulated report state.

    Logic:
    - Store new report content from the current chunk if present
    - Check accumulated report_sections (not just current chunk) for status
    - Analysts with reports = completed
    - First analyst without report = in_progress
    - Remaining analysts without reports = pending
    - When all analysts done, set Bull Researcher to in_progress
    """
    selected = message_buffer.selected_analysts
    found_active = False

    if wall_time_tracker is not None:
        sync_analyst_tracker_from_chunk(wall_time_tracker, chunk)

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        # Capture new report content from current chunk
        if chunk.get(report_key):
            message_buffer.update_report_section(report_key, chunk[report_key])

        # Determine status from accumulated sections, not just current chunk
        has_report = bool(message_buffer.report_sections.get(report_key))

        if has_report:
            message_buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            message_buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            message_buffer.update_agent_status(agent_name, "pending")

    # When all analysts complete, transition research team to in_progress
    if not found_active and selected:
        if message_buffer.agent_status.get("Bull Researcher") == "pending":
            message_buffer.update_agent_status("Bull Researcher", "in_progress")

def extract_content_string(content):
    """Extract string content from various message formats.
    Returns None if no meaningful text content is found.
    """
    import ast

    def is_empty(val):
        """Check if value is empty using Python's truthiness."""
        if val is None or val == '':
            return True
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return True
            try:
                return not bool(ast.literal_eval(s))
            except (ValueError, SyntaxError):
                return False  # Can't parse = real text
        return not bool(val)

    if is_empty(content):
        return None

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get('text', '')
        return text.strip() if not is_empty(text) else None

    if isinstance(content, list):
        text_parts = [
            item.get('text', '').strip() if isinstance(item, dict) and item.get('type') == 'text'
            else (item.strip() if isinstance(item, str) else '')
            for item in content
        ]
        result = ' '.join(t for t in text_parts if t and not is_empty(t))
        return result if result else None

    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message) -> tuple[str, str | None]:
    """Classify LangChain message into display type and extract content.

    Returns:
        (type, content) - type is one of: User, Agent, Data, Control
                        - content is extracted string or None
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, 'content', None))

    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)

    if isinstance(message, ToolMessage):
        return ("Data", content)

    if isinstance(message, AIMessage):
        return ("Agent", content)

    # Fallback for unknown types
    return ("System", content)


def format_tool_args(args, max_length=80) -> str:
    """Format tool arguments for terminal display."""
    result = str(args)
    if len(result) > max_length:
        return result[:max_length - 3] + "..."
    return result


def _load_alpha_state_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_alpha_state_files(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.glob("full_states_log_*.json"))
    return [source]


def _alpha_candidates_from_payload(payload: dict) -> list[AlphaCandidate]:
    alpha_result = payload.get("alpha_mining_result", {}) or {}
    selected = alpha_result.get("selected_alpha", {}) or {}
    candidates_payload = alpha_result.get("candidates", []) or []
    candidates: list[AlphaCandidate] = []

    for candidate_payload in candidates_payload:
        if not isinstance(candidate_payload, dict):
            continue
        candidates.append(
            AlphaCandidate(
                name=str(candidate_payload.get("name", "unknown_alpha")),
                hypothesis=str(candidate_payload.get("hypothesis", "")),
                expression=str(candidate_payload.get("expression", "")),
                signal_score=float(candidate_payload.get("signal_score", 0.0)),
                confidence=float(candidate_payload.get("confidence", 0.0)),
                complexity=int(candidate_payload.get("complexity", 1)),
                validation_status=str(candidate_payload.get("validation_status", "unknown")),
                evidence=[str(item) for item in candidate_payload.get("evidence", [])],
            )
        )

    if not candidates and selected:
        candidates.append(
            AlphaCandidate(
                name=str(selected.get("name", "unknown_alpha")),
                hypothesis=str(selected.get("hypothesis", "")),
                expression=str(selected.get("expression", "")),
                signal_score=float(selected.get("signal_score", 0.0)),
                confidence=float(selected.get("confidence", 0.0)),
                complexity=int(selected.get("complexity", 1)),
                validation_status=str(selected.get("validation_status", "unknown")),
                evidence=[str(item) for item in selected.get("evidence", [])],
            )
        )
    return candidates


def _build_alpha_registry_entry(payload: dict, source_path: Path) -> AlphaRegistryEntry:
    alpha_result = payload.get("alpha_mining_result", {}) or {}
    selected = alpha_result.get("selected_alpha", {}) or {}
    return AlphaRegistryEntry(
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


def _resolve_benchmark_from_default_config(ticker: str) -> str:
    benchmark_map = DEFAULT_CONFIG.get("benchmark_map", {})
    ticker_upper = ticker.upper()
    for suffix, benchmark in benchmark_map.items():
        if suffix and ticker_upper.endswith(suffix.upper()):
            return benchmark
    return benchmark_map.get("", "SPY")

def run_analysis(checkpoint: bool = False):
    # First get all user selections
    selections = get_user_selections()

    # Create config with selected research depth
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = selections["research_depth"]
    config["max_risk_discuss_rounds"] = selections["research_depth"]
    config["quick_think_llm"] = selections["shallow_thinker"]
    config["deep_think_llm"] = selections["deep_thinker"]
    config["backend_url"] = selections["backend_url"]
    config["llm_provider"] = selections["llm_provider"].lower()
    # Provider-specific thinking configuration
    config["google_thinking_level"] = selections.get("google_thinking_level")
    config["openai_reasoning_effort"] = selections.get("openai_reasoning_effort")
    config["anthropic_effort"] = selections.get("anthropic_effort")
    config["output_language"] = selections.get("output_language", "English")
    config["analysis_lookback_days"] = selections.get("analysis_lookback_days", 30)
    config["checkpoint_enabled"] = checkpoint

    # Create stats callback handler for tracking LLM/tool calls
    stats_handler = StatsCallbackHandler()

    # Normalize analyst selection to predefined order (selection is a 'set', order is fixed)
    selected_set = {analyst.value for analyst in selections["analysts"]}
    selected_analyst_keys = [a for a in ANALYST_ORDER if a in selected_set]
    analyst_execution_plan = build_analyst_execution_plan(
        selected_analyst_keys,
        concurrency_limit=config["analyst_concurrency_limit"],
    )
    analyst_wall_time_tracker = AnalystWallTimeTracker(analyst_execution_plan)

    # Initialize the graph with callbacks bound to LLMs
    graph = TradingAgentsGraph(
        selected_analyst_keys,
        config=config,
        debug=True,
        callbacks=[stats_handler],
    )

    # Initialize message buffer with selected analysts
    message_buffer.init_for_analysis(selected_analyst_keys)

    # Track start time for elapsed display
    start_time = time.time()

    # Create result directory
    results_dir = Path(config["results_dir"]) / selections["ticker"] / selections["analysis_date"]
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    def save_message_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, message_type, content = obj.messages[-1]
            content = content.replace("\n", " ")  # Replace newlines with spaces
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [{message_type}] {content}\n")
        return wrapper
    
    def save_tool_call_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, tool_name, args = obj.tool_calls[-1]
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")
        return wrapper

    def save_report_section_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(section_name, content):
            func(section_name, content)
            if section_name in obj.report_sections and obj.report_sections[section_name] is not None:
                content = obj.report_sections[section_name]
                if content:
                    file_name = f"{section_name}.md"
                    text = "\n".join(str(item) for item in content) if isinstance(content, list) else content
                    with open(report_dir / file_name, "w", encoding="utf-8") as f:
                        f.write(text)
        return wrapper

    message_buffer.add_message = save_message_decorator(message_buffer, "add_message")
    message_buffer.add_tool_call = save_tool_call_decorator(message_buffer, "add_tool_call")
    message_buffer.update_report_section = save_report_section_decorator(message_buffer, "update_report_section")

    # Now start the display layout
    layout = create_layout()

    with Live(layout, refresh_per_second=4) as live:
        # Initial display
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Add initial messages
        message_buffer.add_message("System", f"Selected ticker: {selections['ticker']}")
        message_buffer.add_message("System", f"Detected asset type: {selections['asset_type']}")
        message_buffer.add_message(
            "System", f"Analysis date: {selections['analysis_date']}"
        )
        message_buffer.add_message(
            "System",
            f"Selected analysts: {', '.join(analyst.value for analyst in selections['analysts'])}",
        )
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Update agent status to in_progress for the first analyst
        first_analyst = get_initial_analyst_node(analyst_execution_plan)
        message_buffer.update_agent_status(first_analyst, "in_progress")
        analyst_wall_time_tracker.mark_started(selected_analyst_keys[0])
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Create spinner text
        spinner_text = (
            f"Analyzing {selections['ticker']} on {selections['analysis_date']}..."
        )
        update_display(layout, spinner_text, stats_handler=stats_handler, start_time=start_time)

        # Initialize state and get graph args with callbacks
        init_agent_state = graph.propagator.create_initial_state(
            selections["ticker"],
            selections["analysis_date"],
            asset_type=selections["asset_type"],
            analysis_lookback_days=selections.get("analysis_lookback_days", 30),
        )
        # Pass callbacks to graph config for tool execution tracking
        # (LLM tracking is handled separately via LLM constructor)
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        # Stream the analysis
        trace = []
        for chunk in graph.graph.stream(init_agent_state, **args):
            # Process all messages in chunk, deduplicating by message ID
            for message in chunk.get("messages", []):
                msg_id = getattr(message, "id", None)
                if msg_id is not None:
                    if msg_id in message_buffer._processed_message_ids:
                        continue
                    message_buffer._processed_message_ids.add(msg_id)

                msg_type, content = classify_message_type(message)
                if content and content.strip():
                    message_buffer.add_message(msg_type, content)

                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if isinstance(tool_call, dict):
                            message_buffer.add_tool_call(tool_call["name"], tool_call["args"])
                        else:
                            message_buffer.add_tool_call(tool_call.name, tool_call.args)

            # Update analyst statuses based on report state (runs on every chunk)
            update_analyst_statuses(
                message_buffer,
                chunk,
                wall_time_tracker=analyst_wall_time_tracker,
            )

            # Research Team - Handle Investment Debate State
            if chunk.get("investment_debate_state"):
                debate_state = chunk["investment_debate_state"]
                bull_hist = debate_state.get("bull_history", "").strip()
                bear_hist = debate_state.get("bear_history", "").strip()
                judge = debate_state.get("judge_decision", "").strip()

                # Only update status when there's actual content
                if bull_hist or bear_hist:
                    update_research_team_status("in_progress")
                if bull_hist:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}"
                    )
                if bear_hist:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}"
                    )
                if judge:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Research Manager Decision\n{judge}"
                    )
                    update_research_team_status("completed")
                    message_buffer.update_agent_status("Trader", "in_progress")

            # Trading Team
            if chunk.get("trader_investment_plan"):
                message_buffer.update_report_section(
                    "trader_investment_plan", chunk["trader_investment_plan"]
                )
                if message_buffer.agent_status.get("Trader") != "completed":
                    message_buffer.update_agent_status("Trader", "completed")
                    message_buffer.update_agent_status("Aggressive Analyst", "in_progress")

            # Risk Management Team - Handle Risk Debate State
            if chunk.get("risk_debate_state"):
                risk_state = chunk["risk_debate_state"]
                agg_hist = risk_state.get("aggressive_history", "").strip()
                con_hist = risk_state.get("conservative_history", "").strip()
                neu_hist = risk_state.get("neutral_history", "").strip()
                judge = risk_state.get("judge_decision", "").strip()

                if agg_hist:
                    if message_buffer.agent_status.get("Aggressive Analyst") != "completed":
                        message_buffer.update_agent_status("Aggressive Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Aggressive Analyst Analysis\n{agg_hist}"
                    )
                if con_hist:
                    if message_buffer.agent_status.get("Conservative Analyst") != "completed":
                        message_buffer.update_agent_status("Conservative Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Conservative Analyst Analysis\n{con_hist}"
                    )
                if neu_hist:
                    if message_buffer.agent_status.get("Neutral Analyst") != "completed":
                        message_buffer.update_agent_status("Neutral Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Neutral Analyst Analysis\n{neu_hist}"
                    )
                if judge:
                    if message_buffer.agent_status.get("Portfolio Manager") != "completed":
                        message_buffer.update_agent_status("Portfolio Manager", "in_progress")
                        message_buffer.update_report_section(
                            "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
                        )
                        message_buffer.update_agent_status("Aggressive Analyst", "completed")
                        message_buffer.update_agent_status("Conservative Analyst", "completed")
                        message_buffer.update_agent_status("Neutral Analyst", "completed")
                        message_buffer.update_agent_status("Portfolio Manager", "completed")

            # Update the display
            update_display(layout, stats_handler=stats_handler, start_time=start_time)

            trace.append(chunk)

        # Streamed chunks are per-node deltas, not full state. Merge them
        # so every report field populated across the run is present.
        final_state = {}
        for chunk in trace:
            final_state.update(chunk)
        decision = graph.process_signal(final_state["final_trade_decision"])
        graph.curr_state = final_state
        final_state.setdefault("time_context", init_agent_state.get("time_context", {}))
        final_state["data_snapshot"] = DataSnapshot.from_state(final_state).to_log_payload()
        graph.ticker = selections["ticker"]
        graph._log_state(selections["analysis_date"], final_state)

        # Update all agent statuses to completed
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "completed")

        message_buffer.add_message(
            "System", f"Completed analysis for {selections['analysis_date']}"
        )
        message_buffer.add_message("System", analyst_wall_time_tracker.format_summary())

        # Update final report sections
        for section in message_buffer.report_sections.keys():
            if section in final_state:
                message_buffer.update_report_section(section, final_state[section])

        update_display(layout, stats_handler=stats_handler, start_time=start_time)

    # Post-analysis prompts (outside Live context for clean interaction)
    console.print("\n[bold cyan]Analysis Complete![/bold cyan]\n")
    console.print(f"[dim]{analyst_wall_time_tracker.format_summary()}[/dim]")

    # Prompt to save report
    save_choice = typer.prompt("Save report?", default="Y").strip().upper()
    report_save_path = None
    report_file = None
    if save_choice in ("Y", "YES", ""):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = Path.cwd() / "reports" / f"{selections['ticker']}_{timestamp}"
        save_path_str = typer.prompt(
            "Save path (press Enter for default)",
            default=str(default_path)
        ).strip()
        save_path = Path(save_path_str)
        report_save_path = save_path
        try:
            report_file = save_report_to_disk(final_state, selections["ticker"], save_path)
            console.print(f"\n[green]✓ Report saved to:[/green] {save_path.resolve()}")
            console.print(f"  [dim]Complete report:[/dim] {report_file.name}")
        except Exception as e:
            console.print(f"[red]Error saving report: {e}[/red]")

    if report_file is not None:
        eval_choice = typer.prompt(
            "\nEvaluate report against a reference answer?",
            default="N",
        ).strip().upper()
        if eval_choice in ("Y", "YES"):
            if discover_reference_reports():
                reference_path_raw = choose_reference_report()
            else:
                reference_path_raw = typer.prompt(
                    "Reference answer path (.md/.txt/.html/.pdf)",
                    default="",
                ).strip()
            reference_path = Path(reference_path_raw).expanduser()
            if not reference_path_raw or not reference_path.exists():
                console.print("[yellow]Reference answer not found; skipping report evaluation.[/yellow]")
            else:
                topic = typer.prompt(
                    "Evaluation topic label (press Enter to use ticker/date)",
                    default=f"{selections['ticker']} {selections['analysis_date']}",
                ).strip()
                try:
                    evaluator = ReportEvaluator(graph.quick_thinking_llm)
                    evaluation = evaluator.evaluate(
                        report_file.read_text(encoding="utf-8"),
                        load_reference_text(reference_path),
                        topic=topic,
                    )
                    display_report_evaluation(evaluation)
                    final_state["report_evaluation"] = evaluation.model_dump()
                    if report_save_path is not None:
                        evaluation_file = save_report_evaluation_to_disk(evaluation, report_save_path)
                        console.print(f"[green]✓ Report evaluation saved:[/green] {evaluation_file.resolve()}")
                        if report_file is not None:
                            append_report_evaluation_to_report(report_file, evaluation_file)
                            console.print(f"[green]✓ Appended report evaluation to:[/green] {report_file.resolve()}")
                except Exception as e:
                    console.print(f"[red]Error evaluating report: {e}[/red]")

    # Prompt to run a minimal forward backtest for the current historical scenario
    backtest_choice = typer.prompt(
        "\nRun backtest on this analysis result using future historical data?",
        default="N",
    ).strip().upper()
    if backtest_choice in ("Y", "YES"):
        initial_capital_raw = typer.prompt(
            "Initial capital for backtest (press Enter for normalized 1.0)",
            default="1.0",
        ).strip()
        holding_days_raw = typer.prompt(
            "Holding days for backtest (comma-separated)",
            default="5,10,20",
        ).strip()
        try:
            initial_capital = parse_initial_capital_input(initial_capital_raw)
            holding_days_list = parse_holding_days_input(holding_days_raw)
        except ValueError:
            console.print("[yellow]Invalid capital or holding days; using defaults 1.0 and 5,10,20.[/yellow]")
            initial_capital = 1.0
            holding_days_list = [5, 10, 20]

        try:
            backtest_save_dir = None
            if report_save_path is not None:
                backtest_save_dir = report_save_path / "6_backtests"

            summary_results = []
            for holding_days in holding_days_list:
                scenario = BacktestScenario(
                    ticker=selections["ticker"],
                    trade_date=selections["analysis_date"],
                    asset_type=selections["asset_type"],
                )
                backtest_result = graph.run_backtest_from_final_states(
                    [scenario],
                    [final_state],
                    holding_days=holding_days,
                    initial_capital=initial_capital,
                )
                display_backtest_result(
                    backtest_result,
                    selections["ticker"],
                    selections["analysis_date"],
                    holding_days,
                )
                summary_results.append((holding_days, backtest_result))
                if backtest_save_dir is not None:
                    backtest_file = save_backtest_result_to_disk(
                        backtest_result,
                        selections["ticker"],
                        selections["analysis_date"],
                        holding_days,
                        backtest_save_dir,
                    )
                    console.print(f"[green]✓ Backtest saved:[/green] {backtest_file.resolve()}")
            display_backtest_summary(summary_results)
            if backtest_save_dir is not None:
                summary_file = save_backtest_summary_to_disk(
                    summary_results,
                    selections["ticker"],
                    selections["analysis_date"],
                    backtest_save_dir,
                )
                console.print(f"[green]✓ Backtest summary saved:[/green] {summary_file.resolve()}")
                if report_file is not None:
                    append_backtest_summary_to_report(report_file, summary_file)
                    console.print(f"[green]✓ Appended backtest summary to:[/green] {report_file.resolve()}")
        except Exception as e:
            console.print(f"[red]Error running backtest: {e}[/red]")

    alpha_mining_choice = typer.prompt(
        "\nRun alpha mining on this analysis result now?",
        default="N",
    ).strip().upper()
    if alpha_mining_choice in ("Y", "YES"):
        alpha_source = (
            Path(DEFAULT_CONFIG["results_dir"])
            / selections["ticker"]
            / "TradingAgentsStrategy_logs"
            / f"full_states_log_{selections['analysis_date']}.json"
        )
        try:
            registry_file, history_file = run_alpha_mining_for_source(
                alpha_source,
                load_alpha_state_file=_load_alpha_state_file,
                collect_alpha_state_files=_collect_alpha_state_files,
                build_alpha_registry_entry=_build_alpha_registry_entry,
                resolve_benchmark_from_default_config=_resolve_benchmark_from_default_config,
            )
            print_alpha_mining_success(alpha_source, registry_file, history_file)
            registry_rows = AlphaRegistry(registry_file).load()
            history_rows = AlphaMiningHistory(history_file).load()
            final_state["alpha_experience_summary"] = build_alpha_experience_summary(
                registry_rows,
                history_rows,
                selected_alpha=final_state.get("alpha_mining_result", {}).get("selected_alpha", {}),
            )
        except Exception as e:
            console.print(f"[red]Error running alpha mining: {e}[/red]")

    # Prompt to display full report
    display_choice = typer.prompt("\nDisplay full report on screen?", default="Y").strip().upper()
    if display_choice in ("Y", "YES", ""):
        display_complete_report(final_state)


@app.command()
def analyze(
    checkpoint: bool = typer.Option(
        False,
        "--checkpoint",
        help="Enable checkpoint/resume: save state after each node so a crashed run can resume.",
    ),
    clear_checkpoints: bool = typer.Option(
        False,
        "--clear-checkpoints",
        help="Delete all saved checkpoints before running (force fresh start).",
    ),
):
    """Run the standard TradingAgents analysis flow."""
    if clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints
        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        console.print(f"[yellow]Cleared {n} checkpoint(s).[/yellow]")
    run_analysis(checkpoint=checkpoint)


@app.command("evaluate-report")
def evaluate_report(
    report_path: str = typer.Argument(..., help="Path to generated complete_report.md"),
    reference_path: Optional[str] = typer.Argument(None, help="Path to reference answer markdown/text/html/pdf"),
    topic: str = typer.Option("", "--topic", help="Optional topic label for the evaluator"),
    output_path: Optional[str] = typer.Option(
        None,
        "--output",
        help="Optional output path. Defaults to <report_dir>/7_evaluation/report_evaluation.md",
    ),
):
    """Evaluate a saved research report against a reference answer."""
    report_file = Path(report_path).expanduser()
    if reference_path:
        reference_file = Path(reference_path).expanduser()
    else:
        chosen = choose_reference_report() if discover_reference_reports() else ""
        if not chosen:
            console.print("[red]No reference report selected.[/red]")
            raise typer.Exit(code=1)
        reference_file = Path(chosen).expanduser()

    if not report_file.exists():
        console.print(f"[red]Report file not found:[/red] {report_file}")
        raise typer.Exit(code=1)
    if not reference_file.exists():
        console.print(f"[red]Reference answer not found:[/red] {reference_file}")
        raise typer.Exit(code=1)

    config = DEFAULT_CONFIG.copy()
    graph = TradingAgentsGraph(config=config, debug=False)
    evaluator = ReportEvaluator(graph.quick_thinking_llm)
    evaluation = evaluator.evaluate(
        report_file.read_text(encoding="utf-8"),
        load_reference_text(reference_file),
        topic=topic,
    )
    display_report_evaluation(evaluation)

    if output_path:
        destination = Path(output_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_report_evaluation(evaluation), encoding="utf-8")
        saved_path = destination
    else:
        saved_path = save_report_evaluation_to_disk(evaluation, report_file.parent)

    console.print(f"[green]✓ Report evaluation saved:[/green] {saved_path.resolve()}")


@app.command("extract-reference")
def extract_reference(
    html_path: str = typer.Argument(..., help="Path to saved local HTML or PDF report"),
    output_path: Optional[str] = typer.Option(
        None,
        "--output",
        help="Optional markdown/text output path. Defaults to the same filename with .md",
    ),
):
    """Extract readable reference text from a saved local HTML report."""
    source = Path(html_path).expanduser()
    if not source.exists():
        console.print(f"[red]HTML file not found:[/red] {source}")
        raise typer.Exit(code=1)

    if output_path:
        destination = Path(output_path).expanduser()
    else:
        destination = source.with_suffix(".md")

    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix in {".html", ".htm"}:
        text = extract_reference_text_from_html_file(source)
    elif suffix == ".pdf":
        text = extract_reference_text_from_pdf_file(source)
    else:
        console.print(f"[red]Unsupported reference format:[/red] {source.suffix}")
        raise typer.Exit(code=1)

    destination.write_text(text, encoding="utf-8")
    console.print(f"[green]✓ Extracted reference saved:[/green] {destination.resolve()}")


@app.command("mine-alpha")
def mine_alpha(
    source_path: Optional[str] = typer.Argument(None, help="Path to a full_states_log_*.json file or directory"),
    registry_path: Optional[str] = typer.Option(
        None,
        "--registry",
        help="Optional registry JSON path. Defaults to <source_dir>/alpha_registry.json",
    ),
    history_path: Optional[str] = typer.Option(
        None,
        "--history",
        help="Optional history JSON path. Defaults to <source_dir>/alpha_history.json",
    ),
):
    """Mine alpha candidates from saved analysis states and persist the best ones."""
    if source_path:
        source = Path(source_path).expanduser()
    else:
        chosen = choose_alpha_source() if discover_alpha_sources() else ""
        if not chosen:
            console.print("[red]No alpha source selected.[/red]")
            raise typer.Exit(code=1)
        source = Path(chosen).expanduser()
    registry_file_arg = Path(registry_path).expanduser() if registry_path else None
    history_file_arg = Path(history_path).expanduser() if history_path else None
    registry_file, history_file = run_alpha_mining_for_source(
        source,
        registry_path=registry_file_arg,
        history_path=history_file_arg,
        load_alpha_state_file=_load_alpha_state_file,
        collect_alpha_state_files=_collect_alpha_state_files,
        build_alpha_registry_entry=_build_alpha_registry_entry,
        resolve_benchmark_from_default_config=_resolve_benchmark_from_default_config,
    )
    console.print(f"[green]✓ {alpha_text('Alpha mining completed for:', 'Alpha 因子挖掘完成：')}[/green] {source.resolve()}")
    console.print(f"[green]✓ {alpha_text('Registry saved:', 'Registry 已保存：')}[/green] {registry_file.resolve()}")
    console.print(f"[green]✓ {alpha_text('History saved:', 'History 已保存：')}[/green] {history_file.resolve()}")

if __name__ == "__main__":
    app()
