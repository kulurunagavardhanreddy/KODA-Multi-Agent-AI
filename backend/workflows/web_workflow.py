# web_workflow.py

from backend.tools.web_tools import web_search_tool

def run_web_search(query: str) -> str:
    """Executes a web retrieval workflow for the given query."""
    return web_search_tool.invoke({"query": query})
