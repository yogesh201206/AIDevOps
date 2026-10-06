"""
Frontend/Backend API Contract Integration Tests.

Validates that backend endpoint output models strictly satisfy the contracts
and field schemas required by the React frontend components.
Does not make external GitHub calls.
"""

import pytest
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.github import get_github_service
from app.github.service import GitHubService
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


class TestFrontendBackendContract:
    @pytest.mark.asyncio
    async def test_status_contract(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.get_status.return_value = GitHubStatusResponse(
            connected=True,
            username="testuser",
            reason=None,
            rate_limit_remaining=5000,
            rate_limit_reset=1700000000,
            avatar_url="https://avatars.githubusercontent.com/u/1",
        )
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/status")
            assert resp.status_code == 200
            data = resp.json()
            required_keys = {"connected", "username", "reason"}
            assert required_keys.issubset(data.keys())
            assert isinstance(data["connected"], bool)
            assert isinstance(data["username"], str)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_repository_contract(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_repositories.return_value = [
            Repository(
                id=1,
                name="demo",
                full_name="org/demo",
                owner="org",
                private=False,
                html_url="https://github.com/org/demo",
                description="A test repo",
                default_branch="main",
                language="TypeScript",
                stars_count=42,
                forks_count=5,
                open_issues_count=2,
                updated_at="2026-10-06T12:00:00Z",
                pushed_at="2026-10-06T12:05:00Z",
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            resp = await client.get("/api/v1/github/repositories")
            assert resp.status_code == 200
            data = resp.json()
            repo = data[0]
            required_keys = {
                "id",
                "name",
                "full_name",
                "owner",
                "private",
                "default_branch",
                "html_url",
                "language",
                "updated_at",
            }
            assert required_keys.issubset(repo.keys())
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_workflow_runs_and_jobs_contract(self, client: AsyncClient):
        mock_service = AsyncMock(spec=GitHubService)
        mock_service.list_workflow_runs.return_value = [
            WorkflowRun(
                id=99,
                workflow_name="Deploy Pipeline",
                status="completed",
                conclusion="failure",
                branch="main",
                commit_sha="0123456789abcdef",
                commit_short_sha="0123456",
                event="push",
                html_url="https://github.com/org/demo/actions/runs/99",
                is_failed=True,
            )
        ]
        mock_service.list_workflow_run_jobs.return_value = [
            WorkflowJob(
                id=88,
                run_id=99,
                name="Build",
                status="completed",
                conclusion="failure",
                is_failed=True,
                steps=[
                    WorkflowStep(
                        name="Compile",
                        status="completed",
                        conclusion="failure",
                        number=3,
                        is_failed=True,
                    )
                ],
                failed_steps=[
                    WorkflowStep(
                        name="Compile",
                        status="completed",
                        conclusion="failure",
                        number=3,
                        is_failed=True,
                    )
                ],
            )
        ]
        app.dependency_overrides[get_github_service] = lambda: mock_service

        try:
            # Runs contract
            runs_resp = await client.get("/api/v1/github/repositories/org/demo/runs")
            assert runs_resp.status_code == 200
            run_data = runs_resp.json()[0]
            run_keys = {
                "id",
                "workflow_name",
                "status",
                "conclusion",
                "branch",
                "commit_sha",
                "commit_short_sha",
                "is_failed",
            }
            assert run_keys.issubset(run_data.keys())
            assert run_data["is_failed"] is True

            # Jobs contract
            jobs_resp = await client.get("/api/v1/github/repositories/org/demo/runs/99/jobs")
            assert jobs_resp.status_code == 200
            job_data = jobs_resp.json()[0]
            job_keys = {"id", "run_id", "name", "status", "conclusion", "is_failed", "steps", "failed_steps"}
            assert job_keys.issubset(job_data.keys())
            assert job_data["is_failed"] is True
            assert len(job_data["failed_steps"]) == 1
            step = job_data["failed_steps"][0]
            assert {"name", "number", "conclusion", "is_failed"}.issubset(step.keys())
        finally:
            app.dependency_overrides.clear()
