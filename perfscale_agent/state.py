from typing import Annotated, Literal, NotRequired, TypedDict
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
    # Which analysis subgraph is active; used to route tools back to one node only.
    analysis_route: NotRequired[Literal["orion_analysis", "generic_analysis"]]
    # Tool-free consolidated report (Markdown) from the final_report node.
    final_report: NotRequired[str]