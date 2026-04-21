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
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from perfscale_agent.mcp_client import get_mcp_tools
from perfscale_agent.tools.artifact import fetch_artifact
from perfscale_agent.tools.github_pr import fetch_github_pull_request
from perfscale_agent.prow_utils import extract_job_info, set_job_state, passed_condition, get_failed_test
from perfscale_agent.state import AgentState

load_dotenv()

logger = logging.getLogger(__name__)

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
    "Diagnose the failure per the system instructions. "
    "Use fetch_github_pull_request for any https://github.com/.../pull/N links you take from reports."
)


async def create_agent() -> StateGraph:
    """Create the LangGraph diagnosis agent."""

    mcp_tools = await get_mcp_tools()
    tools = TOOLS + mcp_tools # Combined list
    async def prow_job_analysis(state: AgentState) -> dict:
        phase = "initial LLM call" if len(state["messages"]) == 0 else "continuing after tool result(s)"
        logger.info(
            "prow_job_analysis: %s (model=%s)",
            phase,
            MODEL_NAME,
        )
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0,
        )
        agent = llm.bind_tools(tools)
        with open("perfscale_agent/skills/prow-diagnosis-short.md", "r") as f:
            system_prompt = f.read()
        prompt = system_prompt.format(**state,
            artifacts_base=os.getenv("PROW_ARTIFACTS_URL", "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com"),
        )
        if len(state["messages"]) == 0:
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=_USER_TASK),
            ]
        else:
            # Replay opening user turn so AIMessage(tool_calls) is not adjacent to
            # System only (Gemini 400: function call must follow user or tool result).
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=_USER_TASK),
                *state["messages"],
            ]
        logger.info(
            "prow_job_analysis: invoking model (%d message(s) in this request)",
            len(messages),
        )
        response = agent.invoke(messages)
        if response.tool_calls:
            logger.info("Decision: Calling tool '%s'", response.tool_calls[0]['name'])
        return {"messages": [response]}

    workflow = StateGraph(AgentState)

    workflow.add_node("extract_job_info", extract_job_info)
    workflow.add_node("set_job_state", set_job_state)
    workflow.add_node("get_failed_test", get_failed_test)
    workflow.add_node("prow_job_analysis", prow_job_analysis)
    workflow.add_node("tools", ToolNode(tools))


    # Define the flow
    workflow.add_edge(START, "extract_job_info")
    workflow.add_edge("extract_job_info", "set_job_state")
    # Only conditional edges from set_job_state: an unconditional edge here would
    # still schedule get_failed_test even when passed_condition returns END.
    workflow.add_conditional_edges("set_job_state", passed_condition)
    workflow.add_edge("get_failed_test", "prow_job_analysis")
    workflow.add_conditional_edges(
        "prow_job_analysis",
        tools_condition,
    )

    # 3. Link tools back to analysis
    # After the tool runs, Gemini needs to see the result to "diagnose"
    workflow.add_edge("tools", "prow_job_analysis")
    return workflow.compile()
