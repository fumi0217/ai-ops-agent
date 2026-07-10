"""MCP tool for runbook search via RAG."""

from mcp_server.tools.rag import search_runbook as _search


def search_runbook(query: str, top_k: int = 3) -> dict:
    """
    Search operational runbooks by semantic similarity.

    Args:
        query: Natural language query (e.g. 'CPU高騰の対処法', 'service restart procedure').
        top_k: Number of results to return (1–5).
    """
    results = _search(query, top_k=min(top_k, 5))
    if not results:
        return {"results": [], "message": "No matching runbooks found."}
    return {"results": results}
