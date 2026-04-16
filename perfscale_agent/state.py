from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

# AgentState is the state of the agent
class AgentState(TypedDict):
    """State of the agent."""
    messages: Annotated[list, add_messages]
    passed: bool
    job_url: str
    job_name: str
    build_id: str
    failed_step: str
    failed_test: str
    job_result: str
    job_analysis: str
    version_diffs: str