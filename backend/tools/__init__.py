# tools package init

from .web_tools import web_search_tool, product_search_tool
from .calculator_tools import python_repl_tool
from .image_tools import local_places_tool, route_distance_tool
from .rag_tools import get_document_search_tool

def get_agent_tools(user_id: str = ""):
    """Compiles the list of tools the AI Agent is allowed to use, isolated by user."""
    local_tools = [
        web_search_tool,
        local_places_tool,
        product_search_tool,
        get_document_search_tool(user_id),
        python_repl_tool,
        route_distance_tool
    ]
    
    try:
        from backend.integrations.mcp import mcp_manager
        mcp_tools = mcp_manager.get_tools()
        return local_tools + mcp_tools
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("⚠️ [Tools Init] Failed to load MCP tools: %s", e)
        return local_tools
