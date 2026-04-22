"""LangGraph agent for diagnosing OpenShift Perf & Scale issues.

The agent follows a diagnosis workflow:
1. Understand the problem (failed job, regression, etc.)
2. Gather evidence from prow jobs (logs, metrics)
3. Identify payload changes via Sippy
4. Analyze suspect PRs
5. Correlate findings and produce a diagnosis
"""
from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from perfscale_agent.mcp_client import get_mcp_tools
from perfscale_agent.tools.artifact import fetch_artifact
from perfscale_agent.tools.github_pr import fetch_github_pull_request
from perfscale_agent.prow_utils import extract_job_info, set_job_state, passed_condition, get_failed_test
from perfscale_agent.state import AgentState

load_dotenv()

logger = logging.getLogger(__name__)


def _usage_from_ai_message(msg: BaseMessage) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from an AIMessage, or (0, 0) if absent."""
    if not isinstance(msg, AIMessage):
        return (0, 0)
    meta = getattr(msg, "usage_metadata", None)
    if not isinstance(meta, dict):
        return (0, 0)
    inp = meta.get("input_tokens")
    out = meta.get("output_tokens")
    try:
        return (int(inp) if inp is not None else 0, int(out) if out is not None else 0)
    except (TypeError, ValueError):
        return (0, 0)


TOOLS = [
    fetch_artifact,
    fetch_github_pull_request,
]

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "gemini-2.5-pro",
)

# Gemini requires an assistant tool-call turn to follow a *user* turn (or a tool
# result). We only persist AIMessage/ToolMessage in state, so follow-up turns
# must replay the same opening user message before history.
_USER_TASK = (
    "Diagnose this prow job the system instructions"
)


async def create_agent() -> StateGraph:
    """Create the LangGraph diagnosis agent."""

    mcp_tools = await get_mcp_tools()
    tools = TOOLS + mcp_tools   # Combine the tools from the agent and the MCP server
    agent = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
    ).bind_tools(tools)

    async def run_analysis(state: AgentState, prompt_file: str, node_name: str) -> dict:
        logger.info(f"Analysis Node: {node_name}")
        with open(f"perfscale_agent/skills/{prompt_file}", "r") as f:
            system_prompt = f.read()
        prompt = system_prompt.format(**state,
            artifacts_base=os.getenv("PROW_ARTIFACTS_URL", "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com"),
        )
        messages = [SystemMessage(content=prompt), HumanMessage(content=_USER_TASK)]
        if state["messages"]:
            messages.extend(state["messages"])
        logger.info(
            "prow_job_analysis: invoking model (%d message(s) in this request)",
            len(messages),
        )
        response = agent.invoke(messages)
        d_in, d_out = _usage_from_ai_message(response)
        return {
            "messages": [response],
            "input_tokens": state.get("input_tokens", 0) + d_in,
            "output_tokens": state.get("output_tokens", 0) + d_out,
        }

    async def orion_analysis(state: AgentState) -> dict:
        return await run_analysis(state, "orion-analysis.md", "orion_analysis")

    async def generic_analysis(state: AgentState) -> dict:
        return await run_analysis(state, "generic-test-analysis.md", "generic_analysis")

    def _analysis_routes_to_tools(state: AgentState) -> str:
        """Continue to tool execution, or to final report when the model returned text only."""
        msgs = state.get("messages") or []
        last = msgs[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "final_report"

    async def final_report(state: AgentState) -> dict:
        """Single tool-free pass: structured Markdown from the full message history."""
        logger.info("Analysis Node: final_report")
        report_llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=os.getenv("LLM_TEMPERATURE", 0),
            max_tokens=os.getenv("MAX_OUTPUT_TOKENS", 1024),
        )
        with open("perfscale_agent/skills/final-report.md", "r") as f:
            system_prompt = f.read().format(**state)
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "The messages below are the full analysis thread. "
                    "Output the final report per the system template."
                )
            ),
        ]
        messages.extend(state.get("messages", []))
        response = report_llm.invoke(messages)
        d_in, d_out = _usage_from_ai_message(response)
        return {
            "messages": [response],
            "final_report": response.content.strip(),
            "input_tokens": state.get("input_tokens", 0) + d_in,
            "output_tokens": state.get("output_tokens", 0) + d_out,
        }

    def set_analysis_route(state: AgentState) -> dict:
        """Record which analysis branch to use and return to after tools (orion vs generic)."""
        if "orion" in state.get("failed_test", ""):
            return {"analysis_route": "orion_analysis"}
        return {"analysis_route": "generic_analysis"}

    def route_by_analysis_branch(state: AgentState) -> str:
        return state.get("analysis_route", "generic_analysis")

    workflow = StateGraph(AgentState)

    workflow.add_node("extract_job_info", extract_job_info)
    workflow.add_node("set_job_state", set_job_state)
    workflow.add_node("get_failed_test", get_failed_test)
    workflow.add_node("set_analysis_route", set_analysis_route)
    workflow.add_node("orion_analysis", orion_analysis)
    workflow.add_node("generic_analysis", generic_analysis)
    workflow.add_node("final_report", final_report)

    workflow.add_node("tools", ToolNode(tools))

    # Define the flow
    workflow.add_edge(START, "extract_job_info")
    workflow.add_edge("extract_job_info", "set_job_state")
    # Only conditional edges from set_job_state: an unconditional edge here would
    # still schedule get_failed_test even when passed_condition returns END.
    workflow.add_conditional_edges("set_job_state", passed_condition)
    workflow.add_edge("get_failed_test", "set_analysis_route")
    workflow.add_conditional_edges(
        "set_analysis_route",
        route_by_analysis_branch,
        {
            "orion_analysis": "orion_analysis",
            "generic_analysis": "generic_analysis",
        },
    )
    workflow.add_conditional_edges(
        "orion_analysis",
        _analysis_routes_to_tools,
        {"tools": "tools", "final_report": "final_report"},
    )
    workflow.add_conditional_edges(
        "generic_analysis",
        _analysis_routes_to_tools,
        {"tools": "tools", "final_report": "final_report"},
    )

    # Route tools back to the *same* analysis node only (never fan out to both).
    workflow.add_conditional_edges(
        "tools",
        route_by_analysis_branch,
        {
            "orion_analysis": "orion_analysis",
            "generic_analysis": "generic_analysis",
        },
    )
    workflow.add_edge("final_report", END)
    return workflow.compile()
