"""
Chat API — thin FastAPI wrapper around chat/engine.py for the Next.js frontend.

Stateless: the client holds the full `messages` history (raw Gemini content
format, see chat/engine.py) and sends it whole on every request; nothing is
kept in server-side session state (see ADR-0009). `POST /chat` and
`POST /chat/confirm` stream their response as Server-Sent Events instead of a
single JSON body, so the frontend can show MCP tool calls in real time while
the agentic loop is still running (see ADR-0014) — this keeps that real-time
visibility need from requiring a server-side session (e.g. for progress
polling), matching ADR-0009's stateless design. Because the HTTP status is
already committed (200) once the stream starts, failures are surfaced as an
in-stream `error` event rather than an HTTP error status.
"""

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chat import audit
from chat.engine import describe_error, resume_after_confirmation_async, run_conversation_async

app = FastAPI(title="AI Ops Agent Chat API")

# Labels for every MCP tool, not just the mutating ones — used both for the
# confirmation card (_build_pending_action) and for the real-time tool_call
# stream events, so the frontend never needs its own tool-name mapping.
_TOOL_LABELS = {
    "list_services":   "サービス一覧取得",
    "get_metrics":     "メトリクス取得",
    "get_health":      "ヘルスチェック",
    "get_logs":        "ログ取得",
    "get_alerts":      "アラート確認",
    "search_runbook":  "ランブック検索",
    "restart_service": "サービス再起動",
    "scale_service":   "スケール変更",
}

_TOOL_WARNINGS = {
    "restart_service": "⚠️ このサービスは約30秒間停止します。",
    "scale_service":   "⚠️ レプリカ数が変更されます。",
}


def _tool_label(tool_name: str) -> str:
    return _TOOL_LABELS.get(tool_name, tool_name)


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
    raise ValueError(f"_describe_action: unknown mutating tool {tool_name!r}")


def _build_pending_action(raw: dict) -> dict:
    tool_name = raw["tool_name"]
    tool_input = raw["tool_input"]
    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "label": _tool_label(tool_name),
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
    """Shape of the stream's terminal `final` event (see _stream_events)."""
    messages: list[dict[str, Any]]
    reply: str
    pending_action: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/audit-log")
def get_audit_log() -> list[dict[str, Any]]:
    # audit.py only stores the raw tool_name — resolve a display label here,
    # same as _build_pending_action, so the frontend still has no tool-name
    # mapping of its own.
    return [{**entry, "label": _tool_label(entry["tool_name"])} for entry in audit.get_all()]


def _format_sse(data: dict) -> str:
    """
    Wire-format one SSE frame: a `data:` field carrying JSON, terminated by
    the blank line the spec uses to separate frames (see
    frontend/lib/readEventStream.ts, which splits on this same "\n\n"). Kept
    as its own function so the SSE protocol detail doesn't sit inline inside
    event_gen's application logic below.
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_events(run) -> StreamingResponse:
    """
    Run `run(on_pending_action, on_tool_call)` in the background, streaming
    its progress out as Server-Sent Events:
      - `tool_call`: emitted every time engine.py is about to call/finishes
        calling an MCP tool (phase "start"/"end")
      - `final`: the ChatResponse-shaped result, once the turn ends
      - `error`: in place of the old HTTPException(502) — the stream has
        already committed to a 200 status by the time this can happen
    """
    queue: asyncio.Queue = asyncio.Queue()
    pending_holder: list[dict] = []

    def on_pending_action(action: dict) -> None:
        pending_holder.append(action)

    def on_tool_call(event: dict) -> None:
        queue.put_nowait({"type": "tool_call", "label": _tool_label(event["tool_name"]), **event})

    async def runner() -> None:
        try:
            messages, reply = await run(on_pending_action, on_tool_call)
            pending_action = _build_pending_action(pending_holder[0]) if pending_holder else None
            await queue.put({
                "type": "final",
                **ChatResponse(messages=messages, reply=reply, pending_action=pending_action).model_dump(),
            })
        except Exception as exc:
            await queue.put({"type": "error", "detail": describe_error(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def event_gen() -> AsyncIterator[str]:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _format_sse(item)
        # Wait for runner() to actually finish (it already has, in practice,
        # by the time it puts None on the queue); re-raise here only surfaces
        # whatever runner()'s own try/except didn't catch (e.g. CancelledError)
        # so asyncio doesn't just log it as "Task exception was never
        # retrieved" — nothing downstream does anything with it, the response
        # has already committed to a 200.
        await task

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return await _stream_events(
        lambda on_pending, on_tool: run_conversation_async(req.messages, on_pending, on_tool)
    )


@app.post("/chat/confirm")
async def confirm(req: ConfirmRequest) -> StreamingResponse:
    return await _stream_events(
        lambda on_pending, on_tool: resume_after_confirmation_async(
            req.messages, req.pending_action, req.confirmed, on_pending, on_tool
        )
    )
