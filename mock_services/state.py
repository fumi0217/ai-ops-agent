"""In-memory service state for mock microservices."""

import random
import time
from copy import deepcopy
from typing import Any

_BASE_STATE: dict[str, Any] = {
    "api-gateway": {
        "name": "api-gateway",
        "status": "running",
        "replicas": {"current": 3, "desired": 3},
        "metrics": {
            "cpu_percent": 28.4,
            "memory_percent": 41.2,
            "latency_ms": 45,
            "error_rate_percent": 0.1,
            "requests_per_sec": 850,
        },
    },
    "payment-service": {
        "name": "payment-service",
        "status": "degraded",
        "replicas": {"current": 2, "desired": 2},
        "metrics": {
            "cpu_percent": 95.2,
            "memory_percent": 62.0,
            "latency_ms": 450,
            "error_rate_percent": 2.1,
            "requests_per_sec": 120,
        },
    },
    "order-service": {
        "name": "order-service",
        "status": "running",
        "replicas": {"current": 2, "desired": 2},
        "metrics": {
            "cpu_percent": 31.0,
            "memory_percent": 48.5,
            "latency_ms": 90,
            "error_rate_percent": 0.2,
            "requests_per_sec": 340,
        },
    },
    "user-service": {
        "name": "user-service",
        "status": "running",
        "replicas": {"current": 2, "desired": 2},
        "metrics": {
            "cpu_percent": 42.1,
            "memory_percent": 87.6,
            "latency_ms": 130,
            "error_rate_percent": 0.4,
            "requests_per_sec": 210,
        },
    },
    "notification-service": {
        "name": "notification-service",
        "status": "degraded",
        "replicas": {"current": 1, "desired": 2},
        "metrics": {
            "cpu_percent": 55.3,
            "memory_percent": 58.9,
            "latency_ms": 1250,
            "error_rate_percent": 5.8,
            "requests_per_sec": 95,
        },
    },
}

_HEALTHY_METRICS: dict[str, Any] = {
    "api-gateway":          {"cpu_percent": 28.0, "memory_percent": 40.0, "latency_ms": 45,  "error_rate_percent": 0.1, "requests_per_sec": 850},
    "payment-service":      {"cpu_percent": 30.0, "memory_percent": 55.0, "latency_ms": 80,  "error_rate_percent": 0.2, "requests_per_sec": 120},
    "order-service":        {"cpu_percent": 31.0, "memory_percent": 48.0, "latency_ms": 90,  "error_rate_percent": 0.2, "requests_per_sec": 340},
    "user-service":         {"cpu_percent": 40.0, "memory_percent": 50.0, "latency_ms": 100, "error_rate_percent": 0.3, "requests_per_sec": 210},
    "notification-service": {"cpu_percent": 35.0, "memory_percent": 45.0, "latency_ms": 200, "error_rate_percent": 0.5, "requests_per_sec": 95},
}

_state: dict[str, Any] = deepcopy(_BASE_STATE)

_LOG_TEMPLATES: dict[str, list[str]] = {
    "payment-service": [
        "[ERROR] DB connection timeout after 30s (pool exhausted)",
        "[WARN]  CPU throttling detected, processing queue backing up",
        "[ERROR] Request processing time exceeded 400ms SLA threshold",
        "[WARN]  Thread pool at 95% capacity",
        "[INFO]  Health check responded: degraded",
        "[ERROR] Retry attempt 3/3 failed for transaction TX-8821",
    ],
    "notification-service": [
        "[WARN]  Downstream SMTP relay latency: 1200ms",
        "[ERROR] Message queue depth exceeded threshold (>10000)",
        "[WARN]  Consumer lag increasing: 8500 messages pending",
        "[ERROR] Circuit breaker OPEN for email-provider",
        "[INFO]  Replica count mismatch: desired=2 current=1",
    ],
    "user-service": [
        "[WARN]  Heap usage at 87% - GC pressure increasing",
        "[INFO]  Full GC triggered, pause 2.1s",
        "[WARN]  Memory growth rate: +12MB/hr",
        "[INFO]  Cache eviction rate elevated",
    ],
    "api-gateway": [
        "[INFO]  Routing table refreshed (32 routes)",
        "[INFO]  Health checks passed for all upstreams",
        "[DEBUG] Rate limiter: 850 req/s within limits",
    ],
    "order-service": [
        "[INFO]  Order batch processed: 1200 orders/min",
        "[INFO]  DB connection pool: 8/20 active",
    ],
}

_RESTART_LOG = [
    "[INFO]  Received SIGTERM",
    "[INFO]  Graceful shutdown initiated",
    "[INFO]  Draining in-flight requests...",
    "[INFO]  Shutdown complete",
    "[INFO]  Starting up...",
    "[INFO]  Connected to database",
    "[INFO]  Service ready",
]


def get_all_services() -> list[dict]:
    return list(_state.values())


def get_service(name: str) -> dict | None:
    return _state.get(name)


def get_logs(name: str, lines: int = 20, level: str = "all") -> list[str]:
    templates = _LOG_TEMPLATES.get(name, ["[INFO]  Service operating normally"])
    logs = (templates * ((lines // len(templates)) + 1))[:lines]
    if level != "all":
        prefix = f"[{level.upper()}]"
        logs = [l for l in logs if l.startswith(prefix)] or [f"[INFO]  No {level} level logs found"]
    return logs


def get_alerts() -> list[dict]:
    alerts = []
    for svc in _state.values():
        m = svc["metrics"]
        if m["cpu_percent"] > 90:
            alerts.append({"service": svc["name"], "severity": "critical", "message": f"CPU usage critical: {m['cpu_percent']}%"})
        elif m["cpu_percent"] > 70:
            alerts.append({"service": svc["name"], "severity": "warning", "message": f"CPU usage high: {m['cpu_percent']}%"})
        if m["memory_percent"] > 85:
            alerts.append({"service": svc["name"], "severity": "warning", "message": f"Memory usage high: {m['memory_percent']}%"})
        if m["latency_ms"] > 1000:
            alerts.append({"service": svc["name"], "severity": "critical", "message": f"Latency critical: {m['latency_ms']}ms"})
        elif m["latency_ms"] > 500:
            alerts.append({"service": svc["name"], "severity": "warning", "message": f"Latency high: {m['latency_ms']}ms"})
        if m["error_rate_percent"] > 5:
            alerts.append({"service": svc["name"], "severity": "critical", "message": f"Error rate critical: {m['error_rate_percent']}%"})
        if svc["replicas"]["current"] < svc["replicas"]["desired"]:
            alerts.append({"service": svc["name"], "severity": "warning", "message": f"Replica mismatch: {svc['replicas']['current']}/{svc['replicas']['desired']}"})
    return alerts


def restart_service(name: str) -> dict:
    if name not in _state:
        return {"ok": False, "error": f"Service '{name}' not found"}
    svc = _state[name]
    svc["status"] = "running"
    svc["metrics"] = {**_HEALTHY_METRICS[name], "requests_per_sec": svc["metrics"]["requests_per_sec"]}
    return {"ok": True, "message": f"{name} restarted successfully", "logs": _RESTART_LOG}


def scale_service(name: str, replicas: int) -> dict:
    if name not in _state:
        return {"ok": False, "error": f"Service '{name}' not found"}
    if not (1 <= replicas <= 10):
        return {"ok": False, "error": "Replicas must be between 1 and 10"}
    svc = _state[name]
    prev = svc["replicas"]["current"]
    svc["replicas"] = {"current": replicas, "desired": replicas}
    if svc["status"] == "degraded" and replicas >= svc["replicas"]["desired"]:
        svc["status"] = "running"
    return {"ok": True, "message": f"{name} scaled from {prev} to {replicas} replicas"}
