"""MCP tools for read-only metrics and service status."""

import httpx

from mcp_server.config import MOCK_SERVICES_URL


def _get(path: str) -> dict:
    resp = httpx.get(f"{MOCK_SERVICES_URL}{path}", timeout=10)
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
    data = _get(f"/services/{service_name}/metrics")
    if metric_type == "all":
        return data
    key_map = {
        "cpu":        "cpu_percent",
        "memory":     "memory_percent",
        "latency":    "latency_ms",
        "error_rate": "error_rate_percent",
        "rps":        "requests_per_sec",
    }
    key = key_map.get(metric_type)
    if key and key in data.get("metrics", {}):
        return {"service": service_name, metric_type: data["metrics"][key]}
    return data


def get_health(service_name: str) -> dict:
    """Get health status and replica info for a service."""
    return _get(f"/services/{service_name}/health")


def get_alerts() -> dict:
    """Get all active alerts across all services, ordered by severity."""
    return _get("/alerts")
