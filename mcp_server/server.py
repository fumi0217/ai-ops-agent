"""
AI Ops MCP Server — exposes operational tools via MCP protocol (streamable-http).

Run with:
    python -m mcp_server.server
"""

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.logs import get_logs as _get_logs
from mcp_server.tools.metrics import (
    get_alerts as _get_alerts,
    get_health as _get_health,
    get_metrics as _get_metrics,
    list_services as _list_services,
)
from mcp_server.tools.operations import (
    restart_service as _restart_service,
    scale_service as _scale_service,
)
from mcp_server.tools.runbook import search_runbook as _search_runbook

mcp = FastMCP(
    "ai-ops-server",
    instructions=(
        "You are an AI operations assistant. "
        "Use these tools to monitor and operate services. "
        "For mutating operations (restart, scale), always summarize what you are about to do "
        "and wait for explicit user confirmation before executing."
    ),
)


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_services() -> dict:
    """List all services with their current status and replica counts."""
    return _list_services()


@mcp.tool()
def get_metrics(service_name: str, metric_type: str = "all") -> dict:
    """
    Get metrics for a specific service.

    Args:
        service_name: Service name (e.g. 'payment-service', 'api-gateway').
        metric_type: 'all' | 'cpu' | 'memory' | 'latency' | 'error_rate' | 'rps'
    """
    return _get_metrics(service_name, metric_type)


@mcp.tool()
def get_health(service_name: str) -> dict:
    """Get health status and replica counts for a service."""
    return _get_health(service_name)


@mcp.tool()
def get_logs(service_name: str, lines: int = 30, level: str = "all") -> dict:
    """
    Retrieve recent log lines for a service.

    Args:
        service_name: Service name.
        lines: Number of lines (max 100).
        level: 'all' | 'info' | 'warn' | 'error'
    """
    return _get_logs(service_name, lines, level)


@mcp.tool()
def get_alerts() -> dict:
    """Get all active alerts across services, ordered by severity."""
    return _get_alerts()


@mcp.tool()
def search_runbook(query: str, top_k: int = 3) -> dict:
    """
    Search operational runbooks by semantic similarity.
    Use this to find relevant procedures before recommending actions.

    Args:
        query: Natural language query (e.g. 'CPU高騰の対処法', 'high latency troubleshooting').
        top_k: Number of results to return (1–5).
    """
    return _search_runbook(query, top_k)


# ---------------------------------------------------------------------------
# Mutating tools — engine.py intercepts these for user confirmation
# ---------------------------------------------------------------------------

@mcp.tool()
def restart_service(service_name: str, reason: str) -> dict:
    """
    Restart a service. Causes temporary downtime (~30s).
    ALWAYS present the plan to the user and obtain confirmation before calling.

    Args:
        service_name: Service to restart.
        reason: Reason for restart (included in audit log).
    """
    return _restart_service(service_name, reason)


@mcp.tool()
def scale_service(service_name: str, replicas: int, reason: str) -> dict:
    """
    Change the replica count of a service.
    ALWAYS confirm current replica count and present the change before calling.

    Args:
        service_name: Service to scale.
        replicas: Target replica count (1–10).
        reason: Reason for scaling (included in audit log).
    """
    return _scale_service(service_name, replicas, reason)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=8001)
