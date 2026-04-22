from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import BaseTool


async def get_mcp_tools() -> list[BaseTool]:
    client = MultiServerMCPClient(
        {
            "openshift-release": {
                "url": "http://localhost:8000/mcp",
                "transport": "http",
            }
        }
    )
    tools = await client.get_tools()
    return tools