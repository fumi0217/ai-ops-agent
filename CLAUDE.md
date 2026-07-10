# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A portfolio project: an AI ops assistant that lets an operator chat (in Japanese) with an
LLM agent to monitor and operate a simulated microservices platform (5 fake services). The
agent calls tools over MCP; mutating tools require human confirmation in the UI before
executing.

This is a **public portfolio repo** — never commit credentials, API keys, or `.env`.

## Running it

Requires a `.env` (copy from `.env.example`) with `GEMINI_API_KEY` set
(https://aistudio.google.com/app/apikey).

```bash
pip install -r requirements.txt   # installs both requirements-light.txt and requirements-rag.txt

# Build the RAG index once (required before runbook search works)
python -m scripts.index_runbooks

# All three services via Docker
docker-compose up --build
```

Or run each service locally (in separate terminals, in this order):

```bash
uvicorn mock_services.app:app --host 0.0.0.0 --port 8002
python -m mcp_server.server                                   # port 8001
python -m streamlit run chat/app.py --server.port 8000        # UI
```

There is no test suite or linter configured in this repo.

## Architecture

Three services, wired together by `docker-compose.yml`, built from two Docker images:
`Dockerfile.light` (`mock_services` + `chat` — no RAG deps) and `Dockerfile.rag`
(`mcp_server` — pulls in llama-index/chromadb/sentence-transformers, so it's the heavy
one). `requirements.txt` at the repo root just references
`requirements-light.txt` + `requirements-rag.txt` for local dev convenience; each
Dockerfile installs only the split file it needs.

- **`mock_services/`** (port 8002, FastAPI) — simulates a real ops backend. All state
  (`mock_services/state.py`) is in-memory and resets on restart: 5 hardcoded services
  (`api-gateway`, `payment-service`, `order-service`, `user-service`,
  `notification-service`), each with metrics/logs/alerts. `payment-service` and
  `notification-service` start in a "degraded" state on purpose, as a scenario for the
  agent to investigate. Restarting/scaling a service resets its metrics to the
  `_HEALTHY_METRICS` baseline.
- **`mcp_server/`** (port 8001) — a `FastMCP` server (`mcp_server/server.py`) exposing
  ops actions as MCP tools. Read-only tools (`list_services`, `get_metrics`, `get_health`,
  `get_logs`, `get_alerts`) proxy to `mock_services` over HTTP via
  `mcp_server/tools/{logs,metrics}.py`. Mutating tools (`restart_service`,
  `scale_service`, in `mcp_server/tools/operations.py`) also proxy over HTTP but are
  flagged in the tool docstrings as requiring confirmation — enforcement of that
  confirmation actually lives in `chat/engine.py`, not the server. `search_runbook`
  (`mcp_server/tools/runbook.py`) is the one tool that does **not** go over HTTP — it
  imports `mcp_server/tools/rag.py` directly in-process. `mcp_server/tools/rag.py` wraps a
  LlamaIndex `VectorStoreIndex` over a persistent ChromaDB store at `chroma_db/`
  (collection `runbooks`, embeddings via `sentence-transformers/all-MiniLM-L6-v2`).
  It's LLM-free — pure retrieval, returning raw chunks for the agent to reason over.
  The module-level `_index` is a lazy singleton. Because this pulls in
  llama-index/chromadb/sentence-transformers (torch), `mcp_server` is built from a
  separate, heavier image (`Dockerfile.rag`) than `mock_services`/`chat`
  (`Dockerfile.light`) — see `docker-compose.yml`.
  `TransportSecuritySettings` in `server.py` allowlists the `mcp_server` hostname (in
  addition to localhost) since the chat container reaches it as `http://mcp_server:8001`
  under Docker.
- **`chat/`** (port 8000, Streamlit) — the agent loop and UI.
  - `chat/engine.py` is the core: it converts MCP tool schemas to Gemini
    `FunctionDeclaration`s, runs the agentic loop (`_agentic_loop`) against
    `gemini-2.5-flash`, and holds the human-in-the-loop gate: any tool call whose name is
    in `MUTATING_TOOLS` (`restart_service`, `scale_service`) is intercepted *before*
    execution — the loop returns control to the UI with a `pending_action` instead of
    calling the tool. `resume_after_confirmation_async` re-enters the loop after the
    operator approves/denies, injecting a synthetic `function_response`.
  - Message history is stored in `st.session_state.messages` using the raw **Gemini
    content format** (`{"role": "user"|"model", "parts": [...]}`), not a custom chat
    schema — `chat/app.py` and `chat/engine.py` both read/write this shape directly.
    `is_display_message()` decides what's shown: only parts with a `"text"` key are
    rendered; `function_call`/`function_response` parts are history-only and hidden from
    the UI.
  - `chat/app.py` is a standard Streamlit rerun-driven UI: it renders history, then a
    confirmation card (if `pending_action` is set) with per-tool Japanese labels/warnings
    (`_TOOL_LABELS`, `_TOOL_WARNINGS`), then the chat input. Every user action ends in
    `st.rerun()`.
- **`runbooks/`** — markdown runbooks (high CPU, high memory, latency spike, service
  restart) that get chunked/embedded by `scripts/index_runbooks.py` into `chroma_db/`.
  Re-run that script whenever runbook content changes — the chat/MCP process only reads
  the persisted index, it doesn't rebuild it.

## Development workflow

- Always branch off `main` for changes (never commit directly to `main`).
- After making changes, verify them (run/test as applicable) before moving on.
- Present the change and verification result to the user for confirmation.
- Only after the user confirms, present the diff/commit message and get explicit
  go-ahead before `git commit` / `git push`.
- Open a PR back to `main` using the `create-pull-request` skill.

### Adding a new tool

A new ops action needs three pieces kept in sync: the mock endpoint in
`mock_services/app.py` + `state.py`, the MCP tool wrapper in `mcp_server/tools/` +
registration in `mcp_server/server.py`, and — if it's mutating — an entry in
`MUTATING_TOOLS` plus a label/warning in `chat/app.py`'s `_TOOL_LABELS`/`_TOOL_WARNINGS`
so the confirmation card renders correctly.
