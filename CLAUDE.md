# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A portfolio project: an AI ops assistant that lets an operator chat (in Japanese) with an
LLM agent to monitor and operate a simulated microservices platform (5 fake services). The
agent calls tools over MCP; mutating tools require human confirmation in the UI before
executing.

This is a **public portfolio repo** — never commit credentials, API keys, or `.env`.

**Never read or edit `.env`** (only `.env.example`). The user manages `.env` themselves.
Likewise, never print/output the actual value of `GEMINI_API_KEY` (e.g. from a
container's environment) — only check whether it's present/absent (e.g.
`env | grep -q '^GEMINI_API_KEY='`).

Same rule applies to AWS: never read/print real AWS credentials, and never commit
`infra/terraform.tfvars` or `infra/bootstrap/terraform.tfvars` (only the `.example`
files). CI authenticates via GitHub OIDC federation, not static AWS access keys — see
[ADR-0011](docs/adr/0011-github-actions-oidc-cicd.md).

## Running it

Requires a `.env` (copy from `.env.example`) with `GEMINI_API_KEY` set
(https://aistudio.google.com/app/apikey).

```bash
# All four services via Docker — mcp_server rebuilds the RAG index on every
# startup (see docker-compose.yml), so no manual indexing step is needed here.
docker compose up --build
```

Or run each service locally (in separate terminals, in this order; `frontend` also
needs Node.js 20+):

```bash
pip install -r requirements-light.txt -r requirements-rag.txt

# Build the RAG index once (required before runbook search works)
python -m scripts.index_runbooks

uvicorn mock_services.app:app --host 0.0.0.0 --port 8002
uvicorn mcp_server.server:mcp.streamable_http_app --factory --host 0.0.0.0 --port 8001
uvicorn chat.api:app --host 0.0.0.0 --port 8003
```

```bash
cd frontend
npm install
CHAT_API_URL=http://localhost:8003 npm run dev               # UI
```

There is no linter configured for the Python services in this repo (`frontend` has
`next lint`/`next build`'s TypeScript check). Test coverage is partial and scoped to
`chat/engine.py` (see `tests/` and [ADR-0012](docs/adr/0012-pytest-for-chat-engine.md)
for why); nothing else has tests.

```bash
pip install -r requirements-light.txt -r requirements-dev.txt
pytest tests/ -v
```

## Architecture

Four services, wired together by `docker-compose.yml`. The three Python services are
built from two Docker images: `Dockerfile.light` (`mock_services` + `chat_api` — no RAG
deps) and `Dockerfile.rag` (`mcp_server` — pulls in
llama-index/chromadb/sentence-transformers, so it's the heavy one). Each Dockerfile
installs only its own split requirements file (`requirements-light.txt` or
`requirements-rag.txt`); for local dev running all three Python services, install both.
`frontend` is a separate Next.js/Node app with its own `frontend/Dockerfile`.

- **`mock_services/`** (port 8002, FastAPI) — simulates a real ops backend. All state
  (`mock_services/state.py`) is in-memory and resets on restart: 5 hardcoded services
  (`api-gateway`, `payment-service`, `order-service`, `user-service`,
  `notification-service`), each with metrics/logs/alerts. `payment-service` and
  `notification-service` start in a "degraded" state on purpose, as a scenario for the
  agent to investigate. Restarting a service resets its metrics to the
  `_HEALTHY_METRICS` baseline; scaling only updates replica counts (and clears
  "degraded" status if the service was under-replicated) without touching metrics.
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
  separate, heavier image (`Dockerfile.rag`) than `mock_services`/`chat_api`
  (`Dockerfile.light`) — see `docker-compose.yml`.
  `TransportSecuritySettings` in `server.py` allowlists the `mcp_server` hostname (in
  addition to localhost) since the `chat_api` container reaches it as
  `http://mcp_server:8001` under Docker.
- **`chat/`** (port 8003, FastAPI, internal-only — not reachable from the browser) — the
  agent loop and its HTTP API.
  - `chat/engine.py` is the core: it converts MCP tool schemas to Gemini
    `FunctionDeclaration`s, runs the agentic loop (`_agentic_loop`) against
    `gemini-2.5-flash`, and holds the human-in-the-loop gate: any tool call whose name is
    in `MUTATING_TOOLS` (`restart_service`, `scale_service`) is intercepted *before*
    execution — the loop returns control to the caller with a `pending_action` instead of
    calling the tool. If other (non-mutating) tool calls were requested in the same model
    turn, they execute immediately and their responses are held in the pending action's
    `sibling_responses` until confirmation. `resume_after_confirmation_async` re-enters the
    loop after the operator approves/denies, merging `sibling_responses` with the mutating
    tool's own response into one Gemini turn. This logic is covered by
    `tests/test_chat_engine.py`, with the Gemini client and MCP session faked in
    `tests/conftest.py` (see [ADR-0012](docs/adr/0012-pytest-for-chat-engine.md)).
  - `chat/engine.py` is intentionally UI-framework-agnostic: it takes a `messages` list
    (the raw **Gemini content format**, `{"role": "user"|"model", "parts": [...]}`) and
    returns an updated one — no server-side session state. `chat/api.py` is a thin FastAPI
    wrapper around it: `POST /chat` calls `run_conversation_async`, `POST /chat/confirm`
    calls `resume_after_confirmation_async`. Per-tool Japanese labels/warnings
    (`_TOOL_LABELS`, `_TOOL_WARNINGS`) and the confirmation card's description text live
    here too, resolved into the `pending_action` response (`label`/`warning`/
    `description`) so the frontend doesn't need its own copy of tool metadata.
    `is_display_message()`-equivalent filtering (only parts with a `"text"` key are
    user-visible) is ported to the frontend as `frontend/lib/isDisplayMessage.ts`.
- **`frontend/`** (port 8000 externally, Next.js/TypeScript) — the UI. `app/page.tsx` is a
  client component holding `messages`/`pendingAction`/`loading`/`error` in React state (no
  server-side session — the client holds the full history and sends it whole on every
  request, see [ADR-0009](docs/adr/0009-stateless-chat-api.md)). `app/api/chat/route.ts`
  and `app/api/chat/confirm/route.ts` are Route Handlers that proxy to `chat_api` over the
  internal Docker network (`CHAT_API_URL`); the browser never talks to `chat_api` directly,
  so no CORS setup is needed.
- **`runbooks/`** — markdown runbooks (high CPU, high memory, latency spike, service
  restart) that get chunked/embedded by `scripts/index_runbooks.py` into `chroma_db/`.
  `docker-compose.yml`'s `mcp_server` command runs this script on every container
  startup (it drops and recreates the collection), so runbook content changes are
  picked up on the next `docker compose up`/restart. Running the service locally
  (outside Docker) still requires re-running the script manually — see "Running it".

## Infrastructure & CI/CD

- **`infra/`** (Terraform) — a VPC + public subnet + security group (SSH/web allowed only
  from a single `my_ip`) + one EC2 instance, plus 3 ECR repositories (one per actually-built
  Docker image: `light`, `rag`, `frontend` — not one per docker-compose service, since
  `mock_services`/`chat_api` share `Dockerfile.light`'s image). State lives in S3
  (`backend "s3"`, native lockfile locking, no DynamoDB table — see
  [ADR-0010](docs/adr/0010-terraform-state-bootstrap-split.md)).
- **`infra/bootstrap/`** — a separate Terraform root (local state) that creates the
  prerequisites `infra/` needs before CI can touch it at all: the S3 state bucket and the
  GitHub Actions OIDC IAM role. This is the one thing in the whole repo that's applied
  manually, once, with the repo owner's own AWS credentials — CI never runs it (chicken-
  and-egg: CI can't assume a role that doesn't exist yet). See
  [infra/bootstrap/README.md](infra/bootstrap/README.md).
- **`.github/workflows/terraform.yml`** — `terraform plan` on PRs touching `infra/**`
  (excluding `infra/bootstrap/**`, which this workflow never touches; output goes to the
  job summary, not a PR comment), `terraform apply` on push to `main` **or** on a manual
  `workflow_dispatch` from `main` (for a re-apply with no `infra/**` file change — e.g.
  after rotating `TF_VAR_MY_IP`, since the push trigger only fires on an actual diff).
  Passes `TF_VAR_ami` from the `AMI_ID` repo variable — left empty until pinned (see the
  workflow's inline comment): `infra/main.tf` falls back to the latest Amazon Linux 2023
  AMI when unset, which is fine for the very first apply but must be pinned afterwards,
  since changing an `aws_instance`'s AMI forces a destroy+recreate.
  **`.github/workflows/docker-build.yml`** — builds all 3 images on PRs (no push, no AWS
  creds needed); pushing to ECR (tagged `<sha>` and `latest`) is a manual
  `workflow_dispatch` from `main` — this repo has no always-on prod consumer, so trigger
  it by hand right before you actually want to deploy/demo.
  Both authenticate via the same OIDC role (see [ADR-0011](docs/adr/0011-github-actions-oidc-cicd.md)).
  **Neither workflow deploys onto the EC2 instance** — pulling the new images and
  restarting `docker-compose` there is still a manual step today (see
  `docker-compose.prod.yml`'s top-of-file comment for the pull/up command; it's a
  standalone file that references ECR images via `image:` instead of building
  locally, not an override of `docker-compose.yml`).
- Terraform is run locally the same way in both `infra/` and `infra/bootstrap/`:
  `docker run -it --rm -v "$(pwd):/opt" -w /opt --entrypoint ash hashicorp/terraform:latest`
  (no local Terraform install needed).

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
`MUTATING_TOOLS` plus a label/warning in `chat/api.py`'s `_TOOL_LABELS`/`_TOOL_WARNINGS`
so the confirmation card renders correctly (the frontend renders whatever `label`/
`warning`/`description` the API returns — it has no tool-name mapping of its own).
