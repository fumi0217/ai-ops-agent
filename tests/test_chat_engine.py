"""
Tests for chat/engine.py — the agentic loop and the human-in-the-loop gate.

Deliberately scoped: mock_services (mock_services/state.py) is a hand-scripted
demo scenario, so a test that just re-asserts "restart resets metrics" would
only be checking that the scenario still says what it says — not verifying
real behavior. chat/engine.py is different: it's the actual logic deciding
when Gemini's response is trusted to run and when it has to wait for a human,
so that's where tests earn their keep. See docs/adr/0012-pytest-for-chat-engine.md.

No real Gemini API key or MCP server connection is used anywhere in this
file — the genai client and MCP ClientSession are faked (see conftest.py)
so these tests run offline and deterministically.
"""

from unittest.mock import AsyncMock, Mock, call

import httpx
import mcp.types as mcp_types
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from chat import audit, engine
from tests.conftest import AsyncCM, make_genai_response, make_tool_result

# ---------------------------------------------------------------------------
# describe_error
# ---------------------------------------------------------------------------


def test_describe_error_connect_error_blames_mcp_server():
    assert "MCPサーバー" in engine.describe_error(httpx.ConnectError("boom"))


def test_describe_error_timeout_blames_mcp_server():
    assert "MCPサーバー" in engine.describe_error(httpx.TimeoutException("boom"))


def test_describe_error_genai_api_error_blames_the_model():
    err = genai_errors.APIError(code=500, response_json={"error": {"message": "boom"}})
    assert "AIモデル" in engine.describe_error(err)


def test_describe_error_unwraps_exception_group():
    group = ExceptionGroup("multi", [httpx.ConnectError("boom")])
    assert "MCPサーバー" in engine.describe_error(group)


def test_describe_error_unknown_exception_falls_back_to_generic_message():
    assert engine.describe_error(ValueError("whatever")) == (
        "予期しないエラーが発生しました。しばらくしてから再度お試しください。"
    )


# ---------------------------------------------------------------------------
# JSON Schema -> genai Schema / FunctionDeclaration conversion
# ---------------------------------------------------------------------------


def test_json_schema_to_genai_converts_nested_object_and_required():
    # level/tags は現状どのMCPツールも使っていない型(enum/array)だが、
    # _json_schema_to_genai は汎用のJSON Schema変換として書かれているので、
    # 将来Literal型やlist型のパラメータを持つツールが増えても壊れないことを確認する。
    schema = {
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "対象サービス名"},
            "replicas": {"type": "integer"},
            "level": {"type": "string", "enum": ["info", "warning", "error"]},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["service_name"],
    }
    result = engine._json_schema_to_genai(schema)

    assert result.type == genai_types.Type.OBJECT
    assert result.properties["service_name"].type == genai_types.Type.STRING
    assert result.properties["service_name"].description == "対象サービス名"
    assert result.properties["replicas"].type == genai_types.Type.INTEGER
    assert result.properties["level"].enum == ["info", "warning", "error"]
    assert result.properties["tags"].type == genai_types.Type.ARRAY
    assert result.properties["tags"].items.type == genai_types.Type.STRING
    assert result.required == ["service_name"]


def test_mcp_tool_to_genai_without_properties_has_no_parameters():
    tool = mcp_types.Tool(name="list_services", description="一覧を返す", inputSchema={"type": "object"})
    decl = engine._mcp_tool_to_genai(tool)

    assert decl.name == "list_services"
    assert decl.description == "一覧を返す"
    assert decl.parameters is None


def test_mcp_tool_to_genai_with_properties_builds_parameters():
    tool = mcp_types.Tool(
        name="restart_service",
        description="再起動する",
        inputSchema={
            "type": "object",
            "properties": {"service_name": {"type": "string"}},
            "required": ["service_name"],
        },
    )
    decl = engine._mcp_tool_to_genai(tool)

    assert decl.description == "再起動する"
    assert decl.parameters.type == genai_types.Type.OBJECT
    assert "service_name" in decl.parameters.properties


# ---------------------------------------------------------------------------
# is_display_message
# ---------------------------------------------------------------------------


def test_is_display_message_shows_plain_user_text():
    assert engine.is_display_message({"role": "user", "parts": [{"text": "こんにちは"}]}) == (
        True,
        "user",
        "こんにちは",
    )


def test_is_display_message_shows_only_text_when_function_call_present():
    msg = {
        "role": "model",
        "parts": [{"text": "確認します"}, {"function_call": {"name": "get_metrics", "args": {}}}],
    }
    assert engine.is_display_message(msg) == (True, "assistant", "確認します")


def test_is_display_message_hides_function_call_only_turn():
    msg = {"role": "model", "parts": [{"function_call": {"name": "get_metrics", "args": {}}}]}
    show, _, _ = engine.is_display_message(msg)
    assert show is False


def test_is_display_message_hides_function_response_only_turn():
    msg = {"role": "user", "parts": [{"function_response": {"name": "get_metrics", "response": {}}}]}
    show, _, _ = engine.is_display_message(msg)
    assert show is False


# ---------------------------------------------------------------------------
# _call_mcp_tool — on_tool_call start/end events (real-time visibility, ADR-0014)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_mcp_tool_invokes_on_tool_call_for_start_and_end(mock_session):
    mock_session.call_tool.return_value = make_tool_result("cpu: 90%")
    on_tool_call = Mock()

    text, is_error = await engine._call_mcp_tool(
        mock_session, "get_metrics", {"service_name": "payment-service"}, on_tool_call
    )

    assert text == "cpu: 90%"
    assert is_error is False
    assert on_tool_call.call_args_list == [
        call({
            "phase": "start",
            "tool_name": "get_metrics",
            "tool_input": {"service_name": "payment-service"},
        }),
        call({
            "phase": "end",
            "tool_name": "get_metrics",
            "tool_input": {"service_name": "payment-service"},
            "is_error": False,
        }),
    ]


@pytest.mark.asyncio
async def test_call_mcp_tool_without_on_tool_call_still_works(mock_session):
    """on_tool_call is optional — existing call sites that don't pass it must
    keep working (e.g. _agentic_loop's non-mutating-tool path predates it)."""
    mock_session.call_tool.return_value = make_tool_result("cpu: 90%")

    text, is_error = await engine._call_mcp_tool(mock_session, "get_metrics", {"service_name": "x"})

    assert text == "cpu: 90%"
    assert is_error is False


# ---------------------------------------------------------------------------
# _agentic_loop — the core human-in-the-loop gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_final_text_response_ends_the_loop_without_tool_calls(mock_client, mock_session):
    mock_client.aio.models.generate_content.return_value = make_genai_response(texts=["こんにちは"])
    messages = [{"role": "user", "parts": [{"text": "こんにちは"}]}]
    on_pending_action = Mock()

    result_messages, text = await engine._agentic_loop(
        mock_client, mock_session, [], messages, on_pending_action
    )

    assert text == "こんにちは"
    assert result_messages[-1] == {"role": "model", "parts": [{"text": "こんにちは"}]}
    mock_session.call_tool.assert_not_called()
    on_pending_action.assert_not_called()
    assert mock_client.aio.models.generate_content.await_count == 1


@pytest.mark.asyncio
async def test_non_mutating_tool_call_executes_immediately_and_loop_continues(mock_client, mock_session):
    mock_client.aio.models.generate_content.side_effect = [
        make_genai_response(calls=[("get_metrics", {"service_name": "payment-service"})]),
        make_genai_response(texts=["CPUは90%です"]),
    ]
    mock_session.call_tool.return_value = make_tool_result("cpu: 90%")
    messages = [{"role": "user", "parts": [{"text": "payment-serviceの状況は？"}]}]
    on_pending_action = Mock()

    result_messages, text = await engine._agentic_loop(
        mock_client, mock_session, [], messages, on_pending_action
    )

    mock_session.call_tool.assert_awaited_once_with(
        "get_metrics", arguments={"service_name": "payment-service"}
    )
    assert mock_client.aio.models.generate_content.await_count == 2
    # result_messages: [0] original user text, [1] model's function_call turn,
    # [2] the function_response turn, [3] model's final text turn.
    assert len(result_messages) == 4
    assert result_messages[1] == {
        "role": "model",
        "parts": [{"function_call": {"name": "get_metrics", "args": {"service_name": "payment-service"}}}],
    }
    tool_turn = result_messages[2]
    assert tool_turn == {
        "role": "user",
        "parts": [{"function_response": {"name": "get_metrics", "response": {"result": "cpu: 90%"}}}],
    }
    assert result_messages[3] == {"role": "model", "parts": [{"text": "CPUは90%です"}]}
    assert text == "CPUは90%です"
    on_pending_action.assert_not_called()


@pytest.mark.asyncio
async def test_tool_error_is_surfaced_as_error_response_not_result(mock_client, mock_session):
    mock_client.aio.models.generate_content.side_effect = [
        make_genai_response(calls=[("get_metrics", {"service_name": "payment-service"})]),
        make_genai_response(texts=["取得に失敗しました"]),
    ]
    mock_session.call_tool.return_value = make_tool_result("timeout", is_error=True)
    messages = [{"role": "user", "parts": [{"text": "状況を教えて"}]}]

    result_messages, text = await engine._agentic_loop(mock_client, mock_session, [], messages, Mock())

    assert mock_client.aio.models.generate_content.await_count == 2
    fn_response = result_messages[2]["parts"][0]["function_response"]
    assert fn_response["response"] == {"error": "timeout"}
    # ツールエラーを受け取った上でのGeminiの返答であることを確認する
    # ([1]のfunction_call要求自体は前のテストと同じ形なのでここでは見ない)。
    assert result_messages[3] == {"role": "model", "parts": [{"text": "取得に失敗しました"}]}
    assert text == "取得に失敗しました"


@pytest.mark.asyncio
async def test_mutating_tool_call_defers_execution_and_reports_pending_action(mock_client, mock_session):
    mock_client.aio.models.generate_content.return_value = make_genai_response(
        calls=[("restart_service", {"service_name": "payment-service"})]
    )
    messages = [{"role": "user", "parts": [{"text": "再起動して"}]}]
    on_pending_action = Mock()

    result_messages, text = await engine._agentic_loop(
        mock_client, mock_session, [], messages, on_pending_action
    )

    mock_session.call_tool.assert_not_called()
    on_pending_action.assert_called_once_with(
        {
            "tool_name": "restart_service",
            "tool_input": {"service_name": "payment-service"},
            "sibling_responses": [],
        }
    )
    assert text == ""
    # The loop must stop immediately (no follow-up model turn) — the pending
    # action is only resolved later via resume_after_confirmation_async.
    assert mock_client.aio.models.generate_content.await_count == 1


@pytest.mark.asyncio
async def test_mixed_turn_executes_non_mutating_call_and_defers_only_the_mutating_one(
    mock_client, mock_session
):
    mock_client.aio.models.generate_content.return_value = make_genai_response(
        calls=[
            ("get_metrics", {"service_name": "payment-service"}),
            ("restart_service", {"service_name": "payment-service"}),
        ]
    )
    mock_session.call_tool.return_value = make_tool_result("cpu: 95%")
    on_pending_action = Mock()

    await engine._agentic_loop(
        mock_client, mock_session, [], [{"role": "user", "parts": [{"text": "対処して"}]}], on_pending_action
    )

    mock_session.call_tool.assert_awaited_once_with(
        "get_metrics", arguments={"service_name": "payment-service"}
    )
    pending = on_pending_action.call_args.args[0]
    assert pending["tool_name"] == "restart_service"
    assert pending["sibling_responses"] == [
        {"function_response": {"name": "get_metrics", "response": {"result": "cpu: 95%"}}}
    ]


@pytest.mark.asyncio
async def test_second_mutating_call_in_same_turn_is_held_not_auto_executed(mock_client, mock_session):
    mock_client.aio.models.generate_content.return_value = make_genai_response(
        calls=[
            ("restart_service", {"service_name": "payment-service"}),
            ("scale_service", {"service_name": "order-service", "replicas": 3}),
        ]
    )
    on_pending_action = Mock()

    await engine._agentic_loop(
        mock_client, mock_session, [], [{"role": "user", "parts": [{"text": "両方対処して"}]}], on_pending_action
    )

    mock_session.call_tool.assert_not_called()
    pending = on_pending_action.call_args.args[0]
    # Only the first mutating call becomes the pending action...
    assert pending["tool_name"] == "restart_service"
    # ...the second one gets a placeholder response, not a real execution.
    assert pending["sibling_responses"] == [
        {
            "function_response": {
                "name": "scale_service",
                "response": {"result": "他の操作の確認待ちのため保留されました。"},
            }
        }
    ]


# ---------------------------------------------------------------------------
# run_conversation_async / resume_after_confirmation_async — orchestration
# ---------------------------------------------------------------------------


def _wire_fake_mcp(monkeypatch, session, generate_content_response):
    client = Mock()
    client.aio.models.generate_content = AsyncMock(return_value=generate_content_response)
    monkeypatch.setattr(engine.genai, "Client", lambda api_key: client)
    monkeypatch.setattr(engine, "streamablehttp_client", lambda url: AsyncCM((None, None, None)))
    monkeypatch.setattr(engine, "ClientSession", lambda read, write: AsyncCM(session))
    return client


@pytest.mark.asyncio
async def test_run_conversation_async_initializes_session_and_lists_tools_before_calling_gemini(monkeypatch):
    session = AsyncMock()
    session.list_tools.return_value = Mock(tools=[])
    _wire_fake_mcp(monkeypatch, session, make_genai_response(texts=["了解しました"]))

    messages = [{"role": "user", "parts": [{"text": "状況を教えて"}]}]
    _, text = await engine.run_conversation_async(messages, on_pending_action=Mock())

    session.initialize.assert_awaited_once()
    session.list_tools.assert_awaited_once()
    assert text == "了解しました"


@pytest.mark.asyncio
async def test_resume_after_confirmation_confirmed_calls_tool_and_merges_siblings(monkeypatch):
    session = AsyncMock()
    session.list_tools.return_value = Mock(tools=[])
    session.call_tool.return_value = make_tool_result("再起動しました")
    _wire_fake_mcp(monkeypatch, session, make_genai_response(texts=["再起動が完了しました"]))

    pending_action = {
        "tool_name": "restart_service",
        "tool_input": {"service_name": "payment-service"},
        "sibling_responses": [
            {"function_response": {"name": "get_metrics", "response": {"result": "cpu: 95%"}}}
        ],
    }
    messages = [{"role": "user", "parts": [{"text": "再起動して"}]}]

    result_messages, text = await engine.resume_after_confirmation_async(
        messages, pending_action, confirmed=True, on_pending_action=Mock()
    )

    session.call_tool.assert_awaited_once_with(
        "restart_service", arguments={"service_name": "payment-service"}
    )
    merged_turn = result_messages[1]
    assert merged_turn["parts"] == pending_action["sibling_responses"] + [
        {"function_response": {"name": "restart_service", "response": {"result": "再起動しました"}}}
    ]
    assert text == "再起動が完了しました"


@pytest.mark.asyncio
async def test_resume_after_confirmation_denied_skips_the_tool_call(monkeypatch):
    session = AsyncMock()
    session.list_tools.return_value = Mock(tools=[])
    _wire_fake_mcp(monkeypatch, session, make_genai_response(texts=["承知しました、キャンセルします"]))

    pending_action = {
        "tool_name": "restart_service",
        "tool_input": {"service_name": "payment-service"},
        "sibling_responses": [],
    }
    messages = [{"role": "user", "parts": [{"text": "再起動して"}]}]

    result_messages, _ = await engine.resume_after_confirmation_async(
        messages, pending_action, confirmed=False, on_pending_action=Mock()
    )

    session.call_tool.assert_not_called()
    fn_response = result_messages[1]["parts"][0]["function_response"]
    assert fn_response["name"] == "restart_service"
    assert "キャンセル" in fn_response["response"]["result"]


# ---------------------------------------------------------------------------
# chat/audit.py — destructive-op audit log (ADR-0014)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_after_confirmation_confirmed_records_audit_entry(monkeypatch):
    session = AsyncMock()
    session.list_tools.return_value = Mock(tools=[])
    session.call_tool.return_value = make_tool_result("再起動しました")
    _wire_fake_mcp(monkeypatch, session, make_genai_response(texts=["再起動が完了しました"]))

    pending_action = {
        "tool_name": "restart_service",
        "tool_input": {"service_name": "payment-service", "reason": "CPU高騰のため"},
        "sibling_responses": [],
    }
    messages = [{"role": "user", "parts": [{"text": "再起動して"}]}]

    await engine.resume_after_confirmation_async(
        messages, pending_action, confirmed=True, on_pending_action=Mock()
    )

    entries = audit.get_all()
    assert len(entries) == 1
    assert entries[0]["tool_name"] == "restart_service"
    assert entries[0]["tool_input"] == {"service_name": "payment-service", "reason": "CPU高騰のため"}
    assert entries[0]["is_error"] is False
    assert entries[0]["result"] == "再起動しました"
    assert "timestamp" in entries[0]


@pytest.mark.asyncio
async def test_resume_after_confirmation_denied_records_no_audit_entry(monkeypatch):
    session = AsyncMock()
    session.list_tools.return_value = Mock(tools=[])
    _wire_fake_mcp(monkeypatch, session, make_genai_response(texts=["承知しました、キャンセルします"]))

    pending_action = {
        "tool_name": "restart_service",
        "tool_input": {"service_name": "payment-service"},
        "sibling_responses": [],
    }
    messages = [{"role": "user", "parts": [{"text": "再起動して"}]}]

    await engine.resume_after_confirmation_async(
        messages, pending_action, confirmed=False, on_pending_action=Mock()
    )

    assert audit.get_all() == []
