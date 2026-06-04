"""
AI Ops Agent — Streamlit Chat UI

Manages conversation state and renders the human-in-the-loop confirmation dialog
for mutating operations (restart, scale).
"""

import streamlit as st

from chat.engine import resume_after_confirmation, run_conversation

st.set_page_config(page_title="AI Ops Agent", page_icon="🤖", layout="wide")

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

if "error" not in st.session_state:
    st.session_state.error = None

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🤖 AI Ops Agent")
st.caption("チャットで運用作業を自動化 | Powered by Claude + MCP")
st.divider()

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]

    if role == "user" and isinstance(content, str):
        with st.chat_message("user"):
            st.markdown(content)
    elif role == "assistant" and isinstance(content, str):
        with st.chat_message("assistant"):
            st.markdown(content)
    # tool_use / tool_result messages are internal — not displayed

# ---------------------------------------------------------------------------
# Error display
# ---------------------------------------------------------------------------

if st.session_state.error:
    st.error(st.session_state.error)
    st.session_state.error = None

# ---------------------------------------------------------------------------
# Confirmation dialog (rendered above input when pending)
# ---------------------------------------------------------------------------

_TOOL_LABELS = {
    "restart_service": "サービス再起動",
    "scale_service": "スケール変更",
}

_TOOL_WARNINGS = {
    "restart_service": "⚠️ このサービスは約30秒間停止します。",
    "scale_service": "⚠️ レプリカ数が変更されます。",
}


def _describe_action(pending: dict) -> str:
    name = pending["tool_name"]
    inp = pending["tool_input"]
    if name == "restart_service":
        svc = inp.get("service_name", "不明")
        reason = inp.get("reason", "—")
        return f"**{svc}** を再起動します\n\n理由: {reason}"
    if name == "scale_service":
        svc = inp.get("service_name", "不明")
        replicas = inp.get("replicas", "?")
        reason = inp.get("reason", "—")
        return f"**{svc}** を **{replicas}台** にスケール変更します\n\n理由: {reason}"
    return str(inp)


def _on_confirm():
    pending = st.session_state.pending_action
    st.session_state.pending_action = None
    with st.spinner("操作を実行中..."):
        try:
            updated, reply = resume_after_confirmation(
                st.session_state.messages, pending, confirmed=True
            )
            st.session_state.messages = updated
        except Exception as e:
            st.session_state.error = f"エラーが発生しました: {e}"


def _on_cancel():
    pending = st.session_state.pending_action
    st.session_state.pending_action = None
    with st.spinner("キャンセル処理中..."):
        try:
            updated, _ = resume_after_confirmation(
                st.session_state.messages, pending, confirmed=False
            )
            st.session_state.messages = updated
        except Exception as e:
            st.session_state.error = f"エラーが発生しました: {e}"


if st.session_state.pending_action:
    pending = st.session_state.pending_action
    label = _TOOL_LABELS.get(pending["tool_name"], pending["tool_name"])
    warning = _TOOL_WARNINGS.get(pending["tool_name"], "")

    with st.container(border=True):
        st.subheader(f"⚠️ 確認: {label}")
        st.markdown(_describe_action(pending))
        if warning:
            st.warning(warning)
        col1, col2 = st.columns(2)
        with col1:
            st.button("✅ 実行する", on_click=_on_confirm, type="primary", use_container_width=True)
        with col2:
            st.button("❌ キャンセル", on_click=_on_cancel, use_container_width=True)

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

if not st.session_state.pending_action:
    user_input = st.chat_input("例: 全サービスの状況を確認して / payment-serviceのCPUが高い、対処して")

    if user_input:
        # Append and display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Call engine
        pending_holder: list = []

        def _on_pending(action: dict):
            pending_holder.append(action)

        with st.chat_message("assistant"):
            with st.status("考えています...", expanded=True) as status:
                try:
                    updated, reply = run_conversation(
                        st.session_state.messages, _on_pending
                    )
                    st.session_state.messages = updated

                    if pending_holder:
                        st.session_state.pending_action = pending_holder[0]
                        status.update(label="オペレーターの確認が必要です", state="running")
                        st.write("操作を実行する前に確認が必要です。上の確認ダイアログを確認してください。")
                    else:
                        status.update(label="完了", state="complete")
                        if reply:
                            st.markdown(reply)

                except Exception as e:
                    status.update(label="エラー", state="error")
                    st.error(f"エラーが発生しました: {e}")
                    st.session_state.messages.pop()  # remove failed user message

        st.rerun()
