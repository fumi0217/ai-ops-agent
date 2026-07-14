"""Mock microservices API — simulates real operational endpoints."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mock_services import state

app = FastAPI(title="Mock Microservices", version="1.0.0")


class ScaleRequest(BaseModel):
    replicas: int


@app.get("/services")
def list_services():
    return {"services": state.get_all_services()}


@app.get("/services/{name}/metrics")
def get_metrics(name: str, metric_type: str = "all"):
    svc = state.get_service(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    if metric_type == "all":
        return {"service": name, "metrics": svc["metrics"], "status": svc["status"]}
    key = state.METRIC_TYPE_MAP.get(metric_type)
    if not key:
        valid = ", ".join(["all", *state.METRIC_TYPE_MAP])
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metric_type '{metric_type}'. Valid options: {valid}",
        )
    return {"service": name, metric_type: svc["metrics"][key]}


@app.get("/services/{name}/health")
def get_health(name: str):
    svc = state.get_service(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    healthy = svc["status"] == "running"
    return {
        "service": name,
        "healthy": healthy,
        "status": svc["status"],
        "replicas": svc["replicas"],
    }


@app.get("/services/{name}/logs")
def get_logs(name: str, lines: int = 20, level: str = "all"):
    svc = state.get_service(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    logs = state.get_logs(name, lines=min(lines, 100), level=level)
    return {"service": name, "logs": logs}


@app.get("/alerts")
def get_alerts():
    return {"alerts": state.get_alerts()}


@app.post("/services/{name}/restart")
def restart_service(name: str):
    svc = state.get_service(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    logs = state.restart_service(name)
    return {"ok": True, "message": f"{name} restarted successfully", "logs": logs}


@app.post("/services/{name}/scale")
def scale_service(name: str, body: ScaleRequest):
    svc = state.get_service(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    if not (1 <= body.replicas <= 10):
        raise HTTPException(status_code=400, detail="Replicas must be between 1 and 10")
    prev = state.scale_service(name, body.replicas)
    return {"ok": True, "message": f"{name} scaled from {prev} to {body.replicas} replicas"}
