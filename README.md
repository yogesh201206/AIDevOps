# AI DevOps Agent

> **Phase 2 — GitHub Integration**  
> A production-oriented, AI-powered DevOps agent that investigates failed deployments, analyzes GitHub Actions logs, identifies probable root causes, and suggests fixes.

---

## Overview

AI DevOps Agent is built with a clean, extensible architecture. Each phase layers functionality on top of the previous one without requiring structural rewrites.

| Phase | Name | Status |
|-------|------|--------|
| **1** | Foundation | ✅ Complete |
| **2** | GitHub Integration (this release) | ✅ Complete |
| **3** | AI Investigation Engine | Upcoming |
| **4** | Docker & Kubernetes Analysis | Upcoming |
| **5** | Security, CI/CD & Production Hardening | Upcoming |

---

## Architecture

```
Browser ──► React (Vite) ──► FastAPI (Uvicorn) ──► GitHub REST API
              Port 5173          Port 8000               api.github.com
                                   │
                             Pydantic-Settings
                             GitHub Client / Service
                             Structured Error Handling
```

### Security Architecture

- **Token Isolation**: The browser communicates **only** with the FastAPI backend.
- The `GITHUB_TOKEN` is **never** sent to or accessible by the frontend.
- Tokens are loaded strictly into backend process memory via environment variables (`.env`).
- Tokens are excluded from log statements, error payloads, and source code.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, httpx |
| **Frontend** | React 18, Vite, React Router v6, Axios |
| **Testing (backend)** | pytest, pytest-asyncio, httpx (mocked GitHub transport) |
| **Testing (frontend)** | Vitest, Testing Library |
| **DevOps** | Docker, Docker Compose |

---

## Project Structure

```
ai-devops-agent/
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, global exception handler
│   │   ├── config.py            # pydantic-settings configuration
│   │   ├── logging_config.py    # Centralized structured logging
│   │   ├── api/
│   │   │   ├── __init__.py      # Aggregated api_router
│   │   │   ├── health.py        # GET /health, GET /health/ready
│   │   │   └── github.py        # GitHub REST endpoints
│   │   ├── github/
│   │   │   ├── __init__.py      # Module exports
│   │   │   ├── client.py        # Reusable async HTTP client (httpx)
│   │   │   ├── service.py       # Domain logic & schema normalization
│   │   │   ├── schemas.py       # Pydantic models
│   │   │   └── exceptions.py    # Structured GitHub exceptions
│   │   ├── core/
│   │   │   └── __init__.py
│   │   └── models/
│   │       └── __init__.py
│   ├── tests/
│   │   ├── test_health.py       # Liveness/readiness tests
│   │   ├── test_github.py       # GitHub client & endpoint test suite
│   │   └── test_contract.py     # Frontend/Backend contract verification
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pytest.ini
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React Router routes (/ & /repositories)
│   │   ├── main.jsx             # Entry point
│   │   ├── index.css            # Dark slate design system tokens + styling
│   │   ├── components/
│   │   │   ├── Sidebar.jsx      # Navigation sidebar
│   │   │   ├── Topbar.jsx       # Header bar
│   │   │   ├── GitHubStatusCard.jsx # Live connection status banner
│   │   │   ├── RepositoryDetail.jsx # Repo detail with tabs
│   │   │   └── WorkflowRunsView.jsx # Workflow runs, failure & log diagnostics
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # Live system status & overview
│   │   │   ├── Repositories.jsx # Functional repository browser & inspection
│   │   │   └── ComingSoon.jsx   # Phase 3-5 placeholders
│   │   └── services/
│   │       ├── api.js           # Base Axios client & error interceptor
│   │       └── github.js        # GitHub API service functions
│   ├── tests/
│   │   ├── setup.js             # jest-dom setup
│   │   ├── smoke.test.jsx       # App shell & Dashboard smoke tests
│   │   └── repositories.test.jsx# Repositories & Workflow runs tests
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## GitHub Authentication Setup

### 1. Creating a Personal Access Token (PAT)

1. Log into your GitHub account and navigate to **Settings** → **Developer Settings** → **Personal Access Tokens**.
2. Select **Tokens (classic)** or **Fine-grained personal access tokens**.
3. Grant the required permissions:
   - For Classic tokens:
     - `repo` (Full control of private repositories)
     - `actions:read` (View workflow runs and job logs)
   - For Fine-grained tokens:
     - **Repository access**: Select repositories to monitor
     - **Repository permissions**:
       - `Actions`: Read-only
       - `Contents`: Read-only
       - `Metadata`: Read-only
4. Generate and copy the token.

### 2. Configure Local Environment

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

Add your token to `.env`:

```bash
GITHUB_TOKEN=your_token_here
GITHUB_API_URL=https://api.github.com
```

> **Security Note:** Never commit `.env` or paste real tokens in configuration examples, tests, or documentation.

---

## Local Setup & Execution

### 1. Run the Backend

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: **http://localhost:8000**  
Interactive API Documentation: **http://localhost:8000/docs**

### 2. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: **http://localhost:5173**  
Repositories View: **http://localhost:5173/repositories**

---

## Running with Docker Compose

Ensure `.env` exists in the project root:

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| GitHub Status | http://localhost:8000/api/v1/github/status |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## Running Tests

All tests run completely offline and use mocked GitHub responses. Tests pass with or without a configured `GITHUB_TOKEN`.

### Backend Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

**Results**: 38 passed in < 1s (includes health checks, GitHub API endpoints, error handling, and contract tests).

### Frontend Tests

```bash
cd frontend
npm test
```

**Results**: 17 passed across 2 test files (smoke tests and repository/workflow diagnostic tests).

---

## GitHub API Endpoints

All endpoints are mounted under `/api/v1`:

### Connection Health

- `GET /api/v1/github/status`
  - Returns connection state, authenticated username, and rate limit remaining.
  - If unconfigured, returns `connected: false` without crashing.

### Repositories

- `GET /api/v1/github/repositories`
  - Query parameters: `page`, `per_page`, `sort`.
  - Returns accessible repositories for authenticated user.
- `GET /api/v1/github/repositories/{owner}/{repo}`
  - Returns detailed metadata for a single repository.

### Branches & Commits

- `GET /api/v1/github/repositories/{owner}/{repo}/branches`
  - Returns branches and head commit SHAs.
- `GET /api/v1/github/repositories/{owner}/{repo}/commits`
  - Query parameters: `page`, `per_page`.
  - Returns commit history with short SHAs, authors, messages, and dates.

### GitHub Actions

- `GET /api/v1/github/repositories/{owner}/{repo}/workflows`
  - Returns defined Actions workflows.
- `GET /api/v1/github/repositories/{owner}/{repo}/runs`
  - Query parameters: `status`, `branch`, `page`, `per_page`.
  - Returns recent workflow runs with failure flags.
- `GET /api/v1/github/repositories/{owner}/{repo}/runs/{run_id}`
  - Returns detailed run metadata.
- `GET /api/v1/github/repositories/{owner}/{repo}/runs/{run_id}/jobs`
  - Returns jobs and steps, highlighting failed jobs and steps for diagnosis.

### Diagnostics & Failure Logs

- `GET /api/v1/github/repositories/{owner}/{repo}/runs/{run_id}/logs`
  - Query parameters: `max_lines` (default: 500).
  - Retrieves diagnostic log snippets from failed jobs (tail-truncated for performance).
- `GET /api/v1/github/repositories/{owner}/{repo}/jobs/{job_id}/logs`
  - Retrieves log output for a specific job.

---

## Error Handling Standards

All GitHub errors are normalized into consistent application payloads:

```json
{
  "detail": {
    "code": "GITHUB_AUTH_ERROR",
    "message": "GitHub authentication failed. Check your GITHUB_TOKEN."
  }
}
```

Standard Error Codes:
- `GITHUB_NOT_CONFIGURED` (400)
- `GITHUB_AUTH_ERROR` (401)
- `GITHUB_FORBIDDEN` (403)
- `GITHUB_NOT_FOUND` (404)
- `GITHUB_VALIDATION_ERROR` (422)
- `GITHUB_RATE_LIMITED` (429)
- `GITHUB_SERVER_ERROR` (502)
- `GITHUB_NETWORK_ERROR` (503)
- `GITHUB_TIMEOUT` (504)
