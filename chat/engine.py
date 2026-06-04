"""
Chat Engine — orchestrates Claude API with MCP tools and human-in-the-loop confirmation.

Flow:
1. Connect to MCP server and discover tools
2. Build Claude API tool definitions from MCP tool list
3. Run agentic loop (Claude ↔ MCP server)
4. For mutating tools, pause and return pending_action instead of executing
"""

import asyncio
import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
MODEL = "claude-sonnet-4-6"

# Tools that require human confirmation before execution
MUTATING_TOOLS = {"restart_service", "scale_service"}

SYSTEM_PROMPT = """You are an AI operations assistant (AI Ops Agent) for a microservices platform.
You help operators monitor system health, investigate incidents, and perform operational actions.

Your capabilities:
- Check metrics (CPU, memory, latency, error rates) for any service
- Retrieve logs to investigate issues
- Search runbooks for operational guidance
- Restart services or scale them up/down (always requires operator confirmation)

Operating principles:
- When asked to investigate or check status, gather information first, then summarize findings
- When anomalies are found, proactively suggest likely causes and remediation steps based on runbooks
- For destructive operations (restart, scale), always explain what you intend to do and why before proceeding
- After completing a mutating operation, verify the result by re-checking metrics
- Be concise and action-oriented; operators are busy

Current platform: 5 microservices (api-gateway, payment-service, order-service, user-service, notification-service)
"""


def _mcp_tool_to_claude(tool) -> dict:
    """Convert an MCP tool definition to a Claude API tool definition."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
    }


async def _call_mcp_tool(session: ClientSession, tool_name: str, tool_input: dict) -> str:
    """Execute a tool on the MCP server and return the result as a string."""
    result = await session.call_tool(tool_name, arguments=tool_input)
    if result.content:
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else str(result)
    return str(result)


async def run_conversation_async(
    messages: list[dict],
    on_pending_action: callable,
) -> tuple[list[dict], str]:
    """
    Run one turn of the conversation.

    Returns:
        (updated_messages, assistant_text)

    If a mutating tool is requested, calls on_pending_action(action_dict) and
    returns without executing it. The caller must resume after confirmation.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            claude_tools = [_mcp_tool_to_claude(t) for t in tools_result.tools]

            # Prompt cache the stable system prompt
            system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                tools=claude_tools,
                messages=messages,
            )

            # Agentic loop
            while response.stop_reason == "tool_use":
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tool_block in tool_use_blocks:
                    tool_name = tool_block.name
                    tool_input = tool_block.input

                    if tool_name in MUTATING_TOOLS:
                        # Pause — ask operator for confirmation
                        on_pending_action({
                            "tool_use_id": tool_block.id,
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        })
                        # Signal confirmation is pending; caller breaks the loop
                        return messages, _extract_text(response)

                    # Execute read-only tool immediately
                    result_text = await _call_mcp_tool(session, tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result_text,
                    })

                messages.append({"role": "user", "content": tool_results})
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=system,
                    tools=claude_tools,
                    messages=messages,
                )

            # Final text response
            assistant_text = _extract_text(response)
            messages.append({"role": "assistant", "content": assistant_text})
            return messages, assistant_text


async def resume_after_confirmation_async(
    messages: list[dict],
    pending_action: dict,
    confirmed: bool,
) -> tuple[list[dict], str]:
    """
    Resume the conversation after operator confirms or denies a mutating operation.

    If confirmed=True, execute the tool.
    If confirmed=False, tell Claude the operator cancelled.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    if confirmed:
        # Execute the mutating tool
        async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                claude_tools = [_mcp_tool_to_claude(t) for t in tools_result.tools]

                result_text = await _call_mcp_tool(
                    session,
                    pending_action["tool_name"],
                    pending_action["tool_input"],
                )
                tool_results = [{
                    "type": "tool_result",
                    "tool_use_id": pending_action["tool_use_id"],
                    "content": result_text,
                }]
                messages.append({"role": "user", "content": tool_results})

                system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=system,
                    tools=claude_tools,
                    messages=messages,
                )

                # Continue the loop in case Claude calls more tools
                while response.stop_reason == "tool_use":
                    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                    messages.append({"role": "assistant", "content": response.content})

                    tool_results = []
                    for tb in tool_use_blocks:
                        res = await _call_mcp_tool(session, tb.name, tb.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": res,
                        })

                    messages.append({"role": "user", "content": tool_results})
                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        system=system,
                        tools=claude_tools,
                        messages=messages,
                    )

                assistant_text = _extract_text(response)
                messages.append({"role": "assistant", "content": assistant_text})
                return messages, assistant_text
    else:
        # Operator cancelled — inform Claude
        cancel_result = [{
            "type": "tool_result",
            "tool_use_id": pending_action["tool_use_id"],
            "content": json.dumps({"status": "cancelled", "message": "オペレーターによりキャンセルされました"}),
            "is_error": False,
        }]
        messages.append({"role": "user", "content": cancel_result})

        async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                claude_tools = [_mcp_tool_to_claude(t) for t in tools_result.tools]
                system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=system,
                    tools=claude_tools,
                    messages=messages,
                )
                assistant_text = _extract_text(response)
                messages.append({"role": "assistant", "content": assistant_text})
                return messages, assistant_text


def _extract_text(response) -> str:
    return " ".join(b.text for b in response.content if hasattr(b, "text") and b.type == "text")


# Synchronous wrappers for Streamlit (which runs in a sync context)

def run_conversation(messages: list[dict], on_pending_action: callable) -> tuple[list[dict], str]:
    return asyncio.run(run_conversation_async(messages, on_pending_action))


def resume_after_confirmation(
    messages: list[dict],
    pending_action: dict,
    confirmed: bool,
) -> tuple[list[dict], str]:
    return asyncio.run(resume_after_confirmation_async(messages, pending_action, confirmed))
