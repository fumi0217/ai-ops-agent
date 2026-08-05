"""Shared fixtures/helpers for the chat.engine test suite.

These build minimal-but-real instances of the google-genai and mcp SDK
types the code under test actually touches (rather than ad-hoc mocks), so a
test failing because a field name changed upstream is a genuine signal.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import mcp.types as mcp_types
import pytest
from google.genai import types as genai_types


def make_genai_response(texts: list[str] | None = None, calls: list[tuple[str, dict]] | None = None):
    """Build a fake object shaped like the bits of GenerateContentResponse
    _agentic_loop actually reads: response.candidates[0].content.parts."""
    parts = []
    for t in texts or []:
        parts.append(genai_types.Part(text=t))
    for name, args in calls or []:
        parts.append(genai_types.Part(function_call=genai_types.FunctionCall(name=name, args=args)))
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])


def make_tool_result(text: str, is_error: bool = False) -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text=text)],
        isError=is_error,
    )


@pytest.fixture
def mock_session():
    """A fake MCP ClientSession — call_tool is the interesting bit."""
    session = AsyncMock()
    session.call_tool = AsyncMock(return_value=make_tool_result("(unset)"))
    return session


@pytest.fixture
def mock_client():
    """A fake genai.Client — generate_content is set per-test via side_effect."""
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock())))
    return client


class AsyncCM:
    """Minimal async context manager wrapping a fixed value, for stubbing
    streamablehttp_client / ClientSession without a real MCP connection."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False
