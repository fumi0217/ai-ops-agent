"""
Chat API — thin FastAPI wrapper around chat/engine.py for the Next.js frontend.

Stateless: the client holds the full `messages` history (raw Gemini content
format, see chat/engine.py) and sends it whole on every request; nothing is
kept in server-side session state.
"""

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from chat.engine import describe_error, resume_after_confirmation_async, run_conversation_async

app = FastAPI(title="AI Ops Agent Chat API")

_TOOL_LABELS = {
    "restart_service": "サービス再起動",
    "scale_service":   "スケール変更",
}

_TOOL_WARNINGS = {
    "restart_service": "⚠️ このサービスは約30秒間停止します。",
    "scale_service":   "⚠️ レプリカ数が変更されます。",
}


def _describe_action(tool_name: str, tool_input: dict) -> str:
    if tool_name == "restart_service":
        svc    = tool_input.get("service_name", "不明")
        reason = tool_input.get("reason", "—")
        return f"{svc} を再起動します\n\n理由: {reason}"
    if tool_name == "scale_service":
        svc      = tool_input.get("service_name", "不明")
        replicas = tool_input.get("replicas", "?")
        reason   = tool_input.get("reason", "—")
        return f"{svc} を {replicas}台 にスケール変更します\n\n理由: {reason}"
    return str(tool_input)


def _build_pending_action(raw: dict) -> dict:
    tool_name = raw["tool_name"]
    tool_input = raw["tool_input"]
    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "label": _TOOL_LABELS.get(tool_name, tool_name),
        "warning": _TOOL_WARNINGS.get(tool_name, ""),
        "description": _describe_action(tool_name, tool_input),
        "sibling_responses": raw.get("sibling_responses", []),
    }


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]


class ConfirmRequest(BaseModel):
    messages: list[dict[str, Any]]
    pending_action: dict[str, Any]
    confirmed: bool


class ChatResponse(BaseModel):
    messages: list[dict[str, Any]]
    reply: str
    pending_action: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    pending_holder: list[dict] = []

    def on_pending_action(action: dict) -> None:
        pending_holder.append(action)

    try:
        messages, reply = await run_conversation_async(req.messages, on_pending_action)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=describe_error(exc)) from exc

    pending_action = _build_pending_action(pending_holder[0]) if pending_holder else None
    return ChatResponse(messages=messages, reply=reply, pending_action=pending_action)


@app.post("/chat/confirm", response_model=ChatResponse)
async def confirm(req: ConfirmRequest) -> ChatResponse:
    try:
        messages, reply = await resume_after_confirmation_async(
            req.messages, req.pending_action, req.confirmed
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=describe_error(exc)) from exc

    return ChatResponse(messages=messages, reply=reply, pending_action=None)
