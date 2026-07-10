"""MCP tools for read-only metrics and service status."""

import httpx

from mcp_server.config import MOCK_SERVICES_URL


def _get(path: str, params: dict | None = None) -> dict:
    resp = httpx.get(f"{MOCK_SERVICES_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def list_services() -> dict:
    """List all services with their current status and replica counts."""
    return _get("/services")


def get_metrics(service_name: str, metric_type: str = "all") -> dict:
    """
    Get metrics for a specific service.

    Args:
        service_name: Name of the service (e.g. 'payment-service').
        metric_type: One of 'all', 'cpu', 'memory', 'latency', 'error_rate', 'rps'.
    """
    return _get(f"/services/{service_name}/metrics", params={"metric_type": metric_type})


def get_health(service_name: str) -> dict:
    """Get health status and replica info for a service."""
    return _get(f"/services/{service_name}/health")


def get_alerts() -> dict:
    """Get all active alerts across all services, ordered by severity."""
    return _get("/alerts")
