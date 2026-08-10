# rag_workflow.py

from backend.tools.rag_tools import get_document_search_tool

def run_rag_search(query: str, user_id: str) -> str:
    """Executes a RAG retrieval workflow for the given query and user."""
    tool = get_document_search_tool(user_id)
    return tool.invoke({"query": query})
