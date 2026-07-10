"""
Chat Engine — orchestrates Gemini API with MCP tools and human-in-the-loop confirmation.

Message history format (stored in Streamlit session_state):
  [
    {"role": "user",  "parts": [{"text": "..."}]},
    {"role": "model", "parts": [{"text": "..."}, {"function_call": {"name": "...", "args": {...}}}]},
    {"role": "user",  "parts": [{"function_response": {"name": "...", "response": {"result": "..."}}}]},
    {"role": "model", "parts": [{"text": "..."}]},
  ]

Display: only show parts with "text" keys; function_call / function_response parts are internal.
"""

import asyncio
import os
from typing import Any, Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
MODEL = "gemini-2.5-flash"

# Tools that require human confirmation before execution
MUTATING_TOOLS = {"restart_service", "scale_service"}

SYSTEM_INSTRUCTION = """あなたはマイクロサービスプラットフォームのAI運用アシスタント（AI Ops Agent）です。
オペレーターが自然言語でシステムの監視・調査・運用操作を行えるよう支援します。

あなたができること:
- 各サービスのメトリクス確認（CPU、メモリ、レイテンシ、エラー率）
- ログの取得と分析
- ランブック検索による運用手順の参照
- サービスの再起動・スケール変更（必ずオペレーターの確認後に実行）

行動原則:
- 調査依頼には、まず情報収集してから結果を整理して報告してください
- 異常を検知した場合は原因の仮説とランブックに基づく対応策を提示してください
- 破壊的操作（再起動・スケール）は、何をなぜ行うかを説明してから実行してください
- 操作後は必ずメトリクスを再確認して結果を報告してください
- 簡潔かつ行動指向で回答してください

対象プラットフォーム: api-gateway, payment-service, order-service, user-service, notification-service の5サービス
"""


# ---------------------------------------------------------------------------
# Schema conversion helpers
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "string":  "STRING",
    "integer": "INTEGER",
    "number":  "NUMBER",
    "boolean": "BOOLEAN",
    "array":   "ARRAY",
    "object":  "OBJECT",
}


def _json_schema_to_genai(schema: dict) -> types.Schema:
    """Recursively convert a JSON Schema dict to a google.genai Schema."""
    gemini_type = _TYPE_MAP.get(schema.get("type", "string"), "STRING")
    kwargs: dict[str, Any] = {"type": gemini_type}

    if "description" in schema:
        kwargs["description"] = schema["description"]
    if "enum" in schema:
        kwargs["enum"] = [str(e) for e in schema["enum"]]

    if schema.get("type") == "object" and "properties" in schema:
        kwargs["properties"] = {
            k: _json_schema_to_genai(v)
            for k, v in schema["properties"].items()
        }
        if "required" in schema:
            kwargs["required"] = schema["required"]

    if schema.get("type") == "array" and "items" in schema:
        kwargs["items"] = _json_schema_to_genai(schema["items"])

    return types.Schema(**kwargs)


def _mcp_tool_to_genai(tool) -> types.FunctionDeclaration:
    """Convert an MCP tool definition to a Gemini FunctionDeclaration."""
    params = None
    if tool.inputSchema and tool.inputSchema.get("properties"):
        params = _json_schema_to_genai(tool.inputSchema)

    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or "",
        parameters=params,
    )


# ---------------------------------------------------------------------------
# Message history helpers
# ---------------------------------------------------------------------------

def _extract_display_text(messages: list[dict]) -> str:
    """Extract the last model text reply for display."""
    for msg in reversed(messages):
        if msg["role"] == "model":
            texts = [p["text"] for p in msg["parts"] if "text" in p]
            if texts:
                return " ".join(texts)
    return ""


def is_display_message(msg: dict) -> tuple[bool, str, str]:
    """
    Returns (should_display, role_for_ui, text).
    Only pure-text user messages and model messages with text are displayed.
    """
    role = msg["role"]
    parts = msg.get("parts", [])

    has_text = any("text" in p for p in parts)
    has_internal = any("function_call" in p or "function_response" in p for p in parts)

    if not has_text:
        return False, "", ""

    # If it has text AND function_call, show only the text prefix
    text = " ".join(p["text"] for p in parts if "text" in p)

    if role == "user" and not has_internal:
        return True, "user", text
    if role == "model" and has_text:
        return True, "assistant", text

    return False, "", ""


# ---------------------------------------------------------------------------
# MCP tool executor
# ---------------------------------------------------------------------------

async def _call_mcp_tool(session: ClientSession, name: str, args: dict) -> str:
    result = await session.call_tool(name, arguments=args)
    parts = [b.text for b in result.content if hasattr(b, "text")]
    return "\n".join(parts) if parts else "(no result)"


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

async def _agentic_loop(
    client: genai.Client,
    session: ClientSession,
    genai_tools: list[types.FunctionDeclaration],
    messages: list[dict],
    on_pending_action: Callable,
) -> tuple[list[dict], str]:
    """
    Run the Gemini agentic loop.
    Stops when the model produces a final text response,
    or when a mutating tool is requested (stores pending_action and returns).
    """
    tool = types.Tool(function_declarations=genai_tools)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[tool],
        temperature=0.1,
    )

    while True:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=messages,  # type: ignore[arg-type]
            config=config,
        )

        candidate = response.candidates[0]
        raw_parts = candidate.content.parts

        # Split into text and function calls
        text_parts = [p.text for p in raw_parts if p.text]
        func_calls = [p.function_call for p in raw_parts if p.function_call]

        # Build model turn for history
        model_history_parts: list[dict] = []
        if text_parts:
            model_history_parts.extend({"text": t} for t in text_parts)
        for fc in func_calls:
            model_history_parts.append(
                {"function_call": {"name": fc.name, "args": dict(fc.args)}}
            )
        messages.append({"role": "model", "parts": model_history_parts})

        # No function calls → final answer
        if not func_calls:
            return messages, " ".join(text_parts)

        # Check for mutating tools
        for fc in func_calls:
            if fc.name in MUTATING_TOOLS:
                on_pending_action({
                    "tool_name": fc.name,
                    "tool_input": dict(fc.args),
                })
                return messages, " ".join(text_parts)

        # Execute all read-only tool calls
        fn_response_parts: list[dict] = []
        for fc in func_calls:
            result = await _call_mcp_tool(session, fc.name, dict(fc.args))
            fn_response_parts.append({
                "function_response": {
                    "name": fc.name,
                    "response": {"result": result},
                }
            })
        messages.append({"role": "user", "parts": fn_response_parts})


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def run_conversation_async(
    messages: list[dict],
    on_pending_action: Callable,
) -> tuple[list[dict], str]:
    """Run one conversation turn. Returns (updated_messages, last_assistant_text)."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            genai_tools = [_mcp_tool_to_genai(t) for t in tools_result.tools]
            return await _agentic_loop(client, session, genai_tools, messages, on_pending_action)


async def resume_after_confirmation_async(
    messages: list[dict],
    pending_action: dict,
    confirmed: bool,
) -> tuple[list[dict], str]:
    """Resume after operator confirms or denies a mutating operation."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            genai_tools = [_mcp_tool_to_genai(t) for t in tools_result.tools]

            if confirmed:
                result = await _call_mcp_tool(
                    session, pending_action["tool_name"], pending_action["tool_input"]
                )
                fn_response = {
                    "function_response": {
                        "name": pending_action["tool_name"],
                        "response": {"result": result},
                    }
                }
            else:
                fn_response = {
                    "function_response": {
                        "name": pending_action["tool_name"],
                        "response": {"result": "キャンセルされました / Operation cancelled by operator."},
                    }
                }

            messages.append({"role": "user", "parts": [fn_response]})
            return await _agentic_loop(client, session, genai_tools, messages, lambda _: None)


# ---------------------------------------------------------------------------
# Synchronous wrappers for Streamlit
# ---------------------------------------------------------------------------

def run_conversation(
    messages: list[dict],
    on_pending_action: Callable,
) -> tuple[list[dict], str]:
    return asyncio.run(run_conversation_async(messages, on_pending_action))


def resume_after_confirmation(
    messages: list[dict],
    pending_action: dict,
    confirmed: bool,
) -> tuple[list[dict], str]:
    return asyncio.run(resume_after_confirmation_async(messages, pending_action, confirmed))
