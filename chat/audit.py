"""
In-memory audit log of mutating tool executions.

Mirrors the in-memory-state philosophy already used by mock_services/state.py:
resets whenever chat_api restarts — no persistence, this is a portfolio demo,
not a real ops tool. Only entries for MUTATING_TOOLS calls that were actually
confirmed and executed are recorded (see chat/engine.py's
resume_after_confirmation_async); read-only tool calls (metrics, logs, runbook
search) and cancelled confirmations are never logged. No actor/user field —
consistent with ADR-0013 (no auth, single-operator assumption).
"""

from collections import deque
from datetime import datetime, timezone
from typing import Any

_MAX_ENTRIES = 500
_log: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)


def record(tool_name: str, tool_input: dict, is_error: bool, result: str) -> None:
    _log.appendleft({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "is_error": is_error,
        "result": result,
    })


def get_all() -> list[dict[str, Any]]:
    """Newest first (appendleft above keeps this order without extra work)."""
    return list(_log)


def clear() -> None:
    """Test-only: reset the in-memory log between test cases."""
    _log.clear()
