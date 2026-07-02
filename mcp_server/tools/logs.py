"""MCP tools for log retrieval."""

import httpx

from mcp_server.config import MOCK_SERVICES_URL


def get_logs(service_name: str, lines: int = 30, level: str = "all") -> dict:
    """
    Retrieve recent log lines for a service.

    Args:
        service_name: Name of the service.
        lines: Number of log lines to retrieve (max 100).
        level: Filter by log level — 'all', 'info', 'warn', 'error'.
    """
    resp = httpx.get(
        f"{MOCK_SERVICES_URL}/services/{service_name}/logs",
        params={"lines": lines, "level": level},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
