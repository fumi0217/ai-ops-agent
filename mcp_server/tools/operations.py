"""MCP tools for mutating operations (require user confirmation before calling)."""

import httpx

from mcp_server.config import MOCK_SERVICES_URL


def restart_service(service_name: str, reason: str) -> dict:
    """
    Restart a service. IMPORTANT: This is a destructive operation that causes downtime.
    Always present the plan to the user and wait for explicit confirmation before calling.

    Args:
        service_name: Name of the service to restart.
        reason: Reason for the restart (shown to the operator for confirmation).
    """
    resp = httpx.post(
        f"{MOCK_SERVICES_URL}/services/{service_name}/restart",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def scale_service(service_name: str, replicas: int, reason: str) -> dict:
    """
    Scale a service to the specified number of replicas.
    IMPORTANT: Always confirm current replica count and present the change to the user before calling.

    Args:
        service_name: Name of the service to scale.
        replicas: Desired replica count (1-10).
        reason: Reason for scaling (shown to the operator for confirmation).
    """
    resp = httpx.post(
        f"{MOCK_SERVICES_URL}/services/{service_name}/scale",
        json={"replicas": replicas},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
