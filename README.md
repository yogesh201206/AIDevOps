# AI DevOps Agent

> **Phase 3 — AI DevOps Investigation Engine**  
> An automated, production-oriented DevOps agent that investigates failed GitHub Actions workflow runs, processes and sanitizes execution logs, performs root-cause diagnostics via OmniRoute, and provides actionable, evidence-backed recommendations for engineers.

---

## Important Phase 3 Boundary

> [!IMPORTANT]
> **Phase 3 provides analysis and suggested fixes only. No automatic changes are executed.**  
> The agent diagnoses failures, quotes evidence, and suggests concrete fixes, but **NEVER** autonomously applies fixes, executes code modifications, commits to repositories, or alters production infrastructure.

---

## Overview

AI DevOps Agent is built with a modular, layered architecture. Each phase expands capabilities without breaking prior foundations:

| Phase | Name | Status |
|-------|------|--------|
| **1** | Foundation & Health Architecture | ✅ Complete |
| **2** | GitHub Integration (Workflows, Runs, Jobs, Logs) | ✅ Complete |
| **3** | **AI Investigation Engine (OmniRoute, Log Redaction, RCA)** | ✅ **Complete (Current)** |
| **4** | Docker & Kubernetes Intelligence | Upcoming |
| **5** | MCP & Advanced Infrastructure Tooling | Upcoming |

---

## Phase 3 Architecture

```
React Frontend (Port 5173)
       │
       ▼  HTTP REST (FastAPI, Port 8000)
Investigation Service
       │
       ├──► GitHub Service ──► GitHub REST API (Run / Jobs / Logs)
       │
       ├──► Log Processor (ANSI strip, Secret Redaction, Error Hot-Spot Truncation)
       │
       ├──► Investigation Context Builder
       │
       └──► AI Service ──► OmniRoute Client (OpenAI-Compatible Gateway)
                              │
                              ▼  (Port 20128/v1)
                           OmniRoute / LLM
                              │
                              ▼  Structured JSON Output
                        Parser & Pydantic Validation
                              │
       ◄──────────────────────┘  InvestigationResponse
React Investigation UI
```

---

## How AI Investigation Works

1. **Trigger**: An engineer selects a failed workflow run in the Repositories view or enters a repository and run ID on the Investigations page, clicking **"Investigate with AI"**.
2. **Workflow Inspection**: The backend retrieves run details, verifies failure status (successful runs cleanly bypass AI analysis), and extracts all jobs and failed steps.
3. **Preceding Step Extraction**: Preceding steps before failures are included because earlier configuration or installation anomalies frequently cause downstream steps to fail.
4. **Log Retrieval & Secret Redaction**: Diagnostic logs are retrieved and processed through `LogProcessor`:
   - All GitHub tokens (`ghp_`, `github_pat_`), Bearer tokens, private keys, passwords, and connection strings are replaced with `[REDACTED_SECRET]`.
   - ANSI escape codes and terminal artifacts are stripped.
   - Error regions, stack traces, and exit codes are detected.
   - Intelligent windowed truncation preserves the pipeline setup, error regions, and exit code summary while obeying configured context budgets.
5. **Context Synthesis**: `ContextBuilder` formats the workflow metadata and sanitized logs into structured technical incident context.
6. **Inference via OmniRoute**: `OmniRouteClient` sends the structured context with strict senior DevOps system prompts to the configured model through OmniRoute's OpenAI-compatible API (`/v1/chat/completions`).
7. **Schema Validation & Parsing**: The assistant output is parsed and validated against strict Pydantic schemas (`InvestigationResponse`). Overall confidence and root cause confidences must fall between `0.0` and `1.0`.
8. **UI Presentation**: The React dashboard displays the executive summary, root cause cards, expandable evidence snippets, affected components, confidence meters, suggested fixes, and validation checklists.

---

## Security Model

Security is paramount in DevOps tooling:
- **Zero Secrets to Frontend**: API keys (`OMNIROUTE_API_KEY`) and GitHub tokens (`GITHUB_TOKEN`) stay strictly on the backend. No secrets are ever exposed via API responses or frontend bundles.
- **Log Redaction Defense**: Potential secrets, credentials, tokens, and keys in raw execution logs are scrubbed with `LogProcessor.redact_secrets` before prompts are built or sent to any LLM.
- **Read & Suggest Only**: The AI engine produces recommendations for human review. It has no capabilities to autonomously modify code or commit fixes.
- **Safe Structured Logging**: Operational logs contain investigation metadata (run ID, step count, durations), but never log tokens, passwords, or full raw AI prompt texts.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, httpx |
| **AI Abstraction** | OmniRoute (OpenAI-compatible gateway client) |
| **Frontend** | React 18, Vite, React Router v6, Axios |
| **Testing (Backend)** | pytest, pytest-asyncio, httpx (offline mocked transports) |
| **Testing (Frontend)** | Vitest, Testing Library, jsdom |
| **Containerization** | Docker, Docker Compose |

---

## Project Structure

```
ai-devops-agent/
│
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point & global error handlers
│   │   ├── config.py                   # Pydantic settings & OmniRoute configuration
│   │   ├── logging_config.py           # Structured application logging
│   │   ├── api/
│   │   │   ├── __init__.py             # API router aggregation
│   │   │   ├── health.py               # GET /health, GET /health/ready
│   │   │   ├── github.py               # GitHub integration endpoints
│   │   │   ├── ai.py                   # GET /api/v1/ai/status
│   │   │   └── investigations.py       # POST /investigations, GET /investigations
│   │   ├── github/                     # GitHub client, service, schemas, exceptions
│   │   └── services/
│   │       ├── ai/
│   │       │   ├── omniroute_client.py # Reusable OpenAI-compatible HTTP client
│   │       │   ├── ai_service.py       # High-level AI operations & health checks
│   │       │   ├── prompts.py          # DevOps investigator system & user prompts
│   │       │   ├── parser.py           # Robust JSON extractor & Pydantic validation
│   │       │   └── exceptions.py       # AIException, AIUnavailableError, AITimeoutError
│   │       └── investigation/
│   │           ├── log_processor.py    # Secret redaction, ANSI strip, log truncation
│   │           ├── context_builder.py  # Structured prompt context composer
│   │           ├── storage.py          # Investigation history storage repository
│   │           ├── schemas.py          # Pydantic investigation schemas
│   │           └── investigation_service.py # Core investigation orchestration
│   ├── tests/
│   │   ├── test_health.py              # Health endpoint tests
│   │   ├── test_github.py              # GitHub service and endpoint tests
│   │   ├── test_contract.py            # API contract tests (including Phase 3)
│   │   └── test_ai_investigation.py    # 20 comprehensive AI & investigation tests
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pytest.ini
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     # Router routes (/, /repositories, /investigations)
│   │   ├── index.css                   # Global dark-first CSS design tokens & styles
│   │   ├── components/
│   │   │   ├── AIStatusCard.jsx        # OmniRoute connectivity status card
│   │   │   ├── InvestigationResultCard.jsx # Full diagnostic report UI component
│   │   │   ├── WorkflowRunsView.jsx    # Workflow runs, failure diagnostics & AI trigger
│   │   │   ├── GitHubStatusCard.jsx    # GitHub connection status banner
│   │   │   ├── RepositoryDetail.jsx    # Repo detail tabs
│   │   │   ├── Sidebar.jsx             # Left navigation
│   │   │   └── Topbar.jsx              # Application header
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx           # Dashboard overview
│   │   │   ├── Repositories.jsx        # Repository browser & run diagnostics
│   │   │   ├── Investigations.jsx      # Dedicated investigations history & launcher
│   │   │   └── ComingSoon.jsx          # Phase 4-5 placeholders
│   │   └── services/
│   │       ├── api.js                  # Axios client & interceptor
│   │       ├── github.js               # GitHub API client functions
│   │       └── investigations.js       # Investigations & AI status client functions
│   ├── tests/
│   │   ├── smoke.test.jsx              # Navigation and shell smoke tests
│   │   ├── repositories.test.jsx       # Repositories & runs test suite
│   │   └── investigations.test.jsx     # AI status, trigger, and result rendering tests
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions CI workflow
├── docker-compose.yml
├── .env.example
├── LICENSE
└── README.md
```

---

## Configuration & Environment Variables

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | *(empty)* | Personal Access Token with `actions:read`, `repo` permissions |
| `GITHUB_API_URL` | `https://api.github.com` | Base URL for GitHub API |
| `OMNIROUTE_BASE_URL` | `http://localhost:20128/v1` | Base URL for OmniRoute gateway |
| `OMNIROUTE_API_KEY` | *(empty)* | API key if OmniRoute authentication is enabled |
| `OMNIROUTE_MODEL` | `gpt-4o-mini` | AI model identifier to route requests to |
| `OMNIROUTE_TIMEOUT` | `120` | HTTP timeout (in seconds) for AI completions |
| `AI_TEMPERATURE` | `0.1` | Temperature for deterministic diagnostic reasoning |
| `MAX_LOG_CHARS` | `50000` | Maximum character budget for diagnostic logs |
| `MAX_CONTEXT_CHARS` | `30000` | Maximum character budget for prompt context |

---

## OmniRoute Setup

OmniRoute acts as the vendor-agnostic AI provider layer.

### 1. Start OmniRoute
Ensure your OmniRoute instance is running on port 20128:

```bash
# Example if using OmniRoute CLI or container:
omniroute serve --port 20128
```

### 2. Verify OmniRoute Health
Check the OpenAI-compatible `/models` endpoint:

```bash
curl http://localhost:20128/v1/models
```

### 3. Check Backend AI Provider Status
Once the backend is running:

```bash
curl http://localhost:8000/api/v1/ai/status
```

Response:
```json
{
  "configured": true,
  "available": true,
  "provider": "omniroute",
  "model": "gpt-4o-mini"
}
```

*Note: The backend remains fully operational even when OmniRoute is offline. If unreachable, `available` will be `false` without crashing.*

---

## Local Development Execution

### 1. Run the Backend

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Backend API: **http://localhost:8000**
- Interactive Swagger Docs: **http://localhost:8000/docs**

### 2. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

- Frontend Dashboard: **http://localhost:5173**
- Repositories & Runs: **http://localhost:5173/repositories**
- Investigations Page: **http://localhost:5173/investigations**

---

## Running with Docker Compose

To start both the frontend and backend in Docker:

```bash
docker compose up --build
```

For host-to-container communication with a locally running OmniRoute on Linux, `docker-compose.yml` configures `host.docker.internal:host-gateway`.

---

## Testing

All tests are completely offline and use mocked GitHub and OmniRoute transports.

### Run Backend Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

**Results**: 58 passed (covers health endpoints, GitHub integration, OmniRoute client, parser validation, log redaction, large log truncation, context builder, and investigation history).

### Run Frontend Tests

```bash
cd frontend
npm test
```

**Results**: 27 passed across 3 test files (smoke tests, repositories, and AI investigations).

### Build Frontend Bundle

```bash
cd frontend
npm run build
```

---

## Phase 3 REST API Endpoints

### AI Provider Status
- `GET /api/v1/ai/status`
  - Returns `{ "configured": true, "available": true, "provider": "omniroute", "model": "gpt-4o-mini" }`.

### Investigation Endpoints
- `POST /api/v1/investigations`
  - Body: `{ "owner": "org", "repo": "repo-name", "run_id": 12345 }`
  - Dispatches failure analysis, extracts failed steps and preceding steps, sanitizes logs, queries OmniRoute, and returns structured diagnosis.
- `GET /api/v1/investigations`
  - Query parameters: `repository`, `limit`.
  - Returns historical investigation records sorted newest first.
- `GET /api/v1/investigations/{investigation_id}`
  - Returns detailed report for a specific investigation.
