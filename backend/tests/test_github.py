"""
Tests for GitHub integration endpoints and services.

Validates:
  1. GitHub status endpoint (configured, unconfigured, expired token)
  2. Repository listing and details
  3. Branch listing
  4. Commit listing with pagination
  5. GitHub Actions workflow listing
  6. Workflow runs listing and run details
  7. Workflow jobs, identifying failed jobs and failed steps
  8. Log retrieval and truncation handling
  9. Error normalization: 401, 403, 404, 429, timeout, network failure
  10. Contract integrity for frontend consumption
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings
from app.api.github import get_github_service
from app.github.client import GitHubClient
from app.github.service import GitHubService
from app.github.exceptions import (
    GitHubAuthenticationError,
    GitHubNotConfiguredError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubTimeoutError,
    GitHubNetworkError,
)
from app.github.schemas import (
    Branch,
    Commit,
    GitHubStatusResponse,
    Repository,
    Workflow,
    WorkflowJob,
    WorkflowLogs,
    WorkflowRun,
    WorkflowStep,
)


@pytest.fixture
async def client():
    """Async client connected to the ASGI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ── Status Endpoint Tests ──────────────────────────────────────────────────


class TestGitHubStatus:
    async def test_status_unconfigured(self, client: AsyncClient):
        """When GITHUB_TOKEN is not configured, status should report not connected without crashing."""
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_status.return_value = GitHubStatusResponse(
            connected=False,
            reason="GitHub token is not configured",
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert "not configured" in data["reason"].lower()
            assert "token" not in data
        finally:
            app.dependency_overrides.clear()

    async def test_status_connected(self, client: AsyncClient):
        """When GITHUB_TOKEN is valid, status returns connected=True and username."""
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_status.return_value = GitHubStatusResponse(
            connected=True,
            username="octocat",
            rate_limit_remaining=4990,
            rate_limit_reset=1700000000,
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["username"] == "octocat"
            assert data["rate_limit_remaining"] == 4990
        finally:
            app.dependency_overrides.clear()

    async def test_status_auth_error(self, client: AsyncClient):
        """When GITHUB_TOKEN is invalid/expired, status reports connection failure gracefully."""
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_status.return_value = GitHubStatusResponse(
            connected=False,
            reason="GitHub authentication failed: invalid or expired token",
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert "authentication failed" in data["reason"].lower()
        finally:
            app.dependency_overrides.clear()


# ── Repository Endpoints Tests ─────────────────────────────────────────────


class TestRepositories:
    async def test_list_repositories_success(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.return_value = [
            Repository(
                id=101,
                name="devops-agent",
                full_name="org/devops-agent",
                owner="org",
                private=True,
                html_url="https://github.com/org/devops-agent",
                description="DevOps automation",
                default_branch="main",
                language="Python",
                stars_count=10,
                forks_count=2,
                open_issues_count=1,
                updated_at="2026-10-06T10:00:00Z",
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "devops-agent"
            assert data[0]["private"] is True
            assert data[0]["default_branch"] == "main"
        finally:
            app.dependency_overrides.clear()

    async def test_get_repository_details(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_repository.return_value = Repository(
            id=101,
            name="devops-agent",
            full_name="org/devops-agent",
            owner="org",
            private=False,
            html_url="https://github.com/org/devops-agent",
            description="DevOps automation",
            default_branch="main",
            language="Python",
            stars_count=12,
            forks_count=3,
            open_issues_count=0,
            updated_at="2026-10-06T11:00:00Z",
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/devops-agent")
            assert resp.status_code == 200
            data = resp.json()
            assert data["full_name"] == "org/devops-agent"
            assert data["language"] == "Python"
        finally:
            app.dependency_overrides.clear()


# ── Branches & Commits Tests ───────────────────────────────────────────────


class TestBranchesAndCommits:
    async def test_list_branches(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_branches.return_value = [
            Branch(name="main", commit_sha="abcdef1234567890", protected=True),
            Branch(name="develop", commit_sha="1234567890abcdef", protected=False),
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/branches")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["name"] == "main"
            assert data[0]["protected"] is True
        finally:
            app.dependency_overrides.clear()

    async def test_list_commits(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_commits.return_value = [
            Commit(
                sha="9f8e7d6c5b4a3210",
                short_sha="9f8e7d6",
                message="feat: add github integration",
                author="developer",
                date="2026-10-06T11:30:00Z",
                url="https://github.com/org/repo/commit/9f8e7d6c5b4a3210",
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/commits")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["short_sha"] == "9f8e7d6"
            assert data[0]["message"] == "feat: add github integration"
        finally:
            app.dependency_overrides.clear()


# ── GitHub Actions & Failure Detection Tests ───────────────────────────────


class TestGitHubActions:
    async def test_list_workflows(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_workflows.return_value = [
            Workflow(
                id=1,
                name="CI",
                path=".github/workflows/ci.yml",
                state="active",
                html_url="https://github.com/org/repo/actions/workflows/ci.yml",
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/workflows")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "CI"
        finally:
            app.dependency_overrides.clear()

    async def test_list_workflow_runs(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_workflow_runs.return_value = [
            WorkflowRun(
                id=5001,
                workflow_name="Deploy",
                status="completed",
                conclusion="failure",
                branch="main",
                commit_sha="a1b2c3d4e5f6",
                commit_short_sha="a1b2c3d",
                event="push",
                html_url="https://github.com/org/repo/actions/runs/5001",
                is_failed=True,
            ),
            WorkflowRun(
                id=5002,
                workflow_name="Deploy",
                status="completed",
                conclusion="success",
                branch="main",
                commit_sha="b2c3d4e5f6a1",
                commit_short_sha="b2c3d4e",
                event="push",
                html_url="https://github.com/org/repo/actions/runs/5002",
                is_failed=False,
            ),
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["is_failed"] is True
            assert data[1]["is_failed"] is False
        finally:
            app.dependency_overrides.clear()

    async def test_get_workflow_run_details(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_workflow_run.return_value = WorkflowRun(
            id=5001,
            workflow_name="Deploy",
            status="completed",
            conclusion="failure",
            branch="main",
            commit_sha="a1b2c3d4e5f6",
            commit_short_sha="a1b2c3d",
            event="push",
            html_url="https://github.com/org/repo/actions/runs/5001",
            is_failed=True,
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/runs/5001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == 5001
            assert data["is_failed"] is True
        finally:
            app.dependency_overrides.clear()

    async def test_workflow_jobs_and_failure_detection(self, client: AsyncClient):
        """Tests that failed jobs and failed steps are accurately flagged."""
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_workflow_run_jobs.return_value = [
            WorkflowJob(
                id=901,
                run_id=5001,
                name="build-and-test",
                status="completed",
                conclusion="failure",
                is_failed=True,
                steps=[
                    WorkflowStep(
                        name="Set up Python",
                        status="completed",
                        conclusion="success",
                        number=1,
                        is_failed=False,
                    ),
                    WorkflowStep(
                        name="Run Pytest",
                        status="completed",
                        conclusion="failure",
                        number=2,
                        is_failed=True,
                    ),
                ],
                failed_steps=[
                    WorkflowStep(
                        name="Run Pytest",
                        status="completed",
                        conclusion="failure",
                        number=2,
                        is_failed=True,
                    )
                ],
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/runs/5001/jobs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            job = data[0]
            assert job["is_failed"] is True
            assert len(job["failed_steps"]) == 1
            assert job["failed_steps"][0]["name"] == "Run Pytest"
            assert job["failed_steps"][0]["number"] == 2
            assert job["failed_steps"][0]["conclusion"] == "failure"
        finally:
            app.dependency_overrides.clear()

    async def test_workflow_logs_retrieval(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_workflow_run_logs.return_value = WorkflowLogs(
            run_id=5001,
            job_id=901,
            available=True,
            content="FAILED tests/test_app.py::test_database - AssertionError\n1 failed",
            truncated=False,
            total_lines=2,
            message="Displaying logs from job: 'build-and-test'",
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/repo/runs/5001/logs")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert "AssertionError" in data["content"]
            assert data["truncated"] is False
        finally:
            app.dependency_overrides.clear()


# ── Error Handling Tests ───────────────────────────────────────────────────


class TestGitHubErrors:
    async def test_missing_token_error(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.side_effect = GitHubNotConfiguredError()
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 400
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_NOT_CONFIGURED"
        finally:
            app.dependency_overrides.clear()

    async def test_401_unauthorized(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.side_effect = GitHubAuthenticationError("Bad credentials")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 401
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_AUTH_ERROR"
        finally:
            app.dependency_overrides.clear()

    async def test_403_forbidden(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_repository.side_effect = GitHubPermissionError("Resource inaccessible")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/secret-repo")
            assert resp.status_code == 403
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_FORBIDDEN"
        finally:
            app.dependency_overrides.clear()

    async def test_404_not_found(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_repository.side_effect = GitHubNotFoundError("Repo not found")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories/org/nonexistent")
            assert resp.status_code == 404
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    async def test_429_rate_limited(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.side_effect = GitHubRateLimitError("Rate limit exceeded")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 429
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_RATE_LIMITED"
        finally:
            app.dependency_overrides.clear()

    async def test_timeout_error(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.side_effect = GitHubTimeoutError("Connection timed out")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 504
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_TIMEOUT"
        finally:
            app.dependency_overrides.clear()

    async def test_network_error(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.side_effect = GitHubNetworkError("DNS resolution failed")
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 503
            data = resp.json()
            assert data["detail"]["code"] == "GITHUB_NETWORK_ERROR"
        finally:
            app.dependency_overrides.clear()


# ── Unit Tests for GitHubClient & Service Normalization ────────────────────


class TestClientAndServiceUnit:
    @pytest.mark.asyncio
    async def test_service_parses_jobs_and_failed_steps(self):
        """Test Service correctly maps raw GitHub API JSON payloads into schemas."""
        mock_raw_jobs = {
            "total_count": 1,
            "jobs": [
                {
                    "id": 1234,
                    "name": "integration-test",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/actions/jobs/1234",
                    "steps": [
                        {
                            "name": "Checkout code",
                            "status": "completed",
                            "conclusion": "success",
                            "number": 1,
                        },
                        {
                            "name": "Run tests",
                            "status": "completed",
                            "conclusion": "failure",
                            "number": 2,
                        },
                    ],
                }
            ],
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_json.return_value = mock_raw_jobs

        service = GitHubService(client=mock_client)
        jobs = await service.list_workflow_run_jobs("org", "repo", 555)

        assert len(jobs) == 1
        job = jobs[0]
        assert job.is_failed is True
        assert len(job.steps) == 2
        assert len(job.failed_steps) == 1
        assert job.failed_steps[0].name == "Run tests"
        assert job.failed_steps[0].is_failed is True

    @pytest.mark.asyncio
    async def test_service_log_truncation(self):
        """Test logs exceeding max_lines are truncated cleanly."""
        long_log = "\n".join([f"Line {i}: log message" for i in range(100)])

        mock_response = httpx.Response(
            status_code=200,
            text=long_log,
            request=httpx.Request("GET", "https://api.github.com/repos/org/repo/actions/jobs/1/logs"),
        )
        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_raw.return_value = mock_response

        service = GitHubService(client=mock_client)
        logs = await service.get_job_logs("org", "repo", job_id=1, max_lines=20)

        assert logs.available is True
        assert logs.truncated is True
        assert logs.total_lines == 100
        assert "Line 99: log message" in logs.content
        assert "Line 0: log message" not in logs.content
