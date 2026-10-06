"""
GitHub API endpoints.

Exposes REST endpoints for inspecting GitHub repositories, commits,
branches, Actions workflows, runs, jobs, and failure logs.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.github.schemas import (
    Branch,
    Commit,
    GitHubErrorResponse,
    GitHubStatusResponse,
    Repository,
    Workflow,
    WorkflowJob,
    WorkflowLogs,
    WorkflowRun,
)
from app.github.service import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["GitHub"])


def get_github_service() -> GitHubService:
    """Dependency providing a GitHubService instance."""
    return GitHubService()


# ── Status ───────────────────────────────────────────────────────────────────


@router.get(
    "/status",
    response_model=GitHubStatusResponse,
    summary="GitHub connection status",
    description="Check whether GitHub integration is configured and authenticated.",
)
async def get_github_status(
    service: GitHubService = Depends(get_github_service),
) -> GitHubStatusResponse:
    return await service.get_status()


# ── Repositories ─────────────────────────────────────────────────────────────


@router.get(
    "/repositories",
    response_model=List[Repository],
    responses={400: {"model": GitHubErrorResponse}, 401: {"model": GitHubErrorResponse}},
    summary="List accessible repositories",
    description="Retrieve repositories accessible to the authenticated GitHub user with pagination.",
)
async def list_repositories(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    sort: str = Query("updated", description="Sort field: created, updated, pushed, full_name"),
    service: GitHubService = Depends(get_github_service),
) -> List[Repository]:
    return await service.list_repositories(page=page, per_page=per_page, sort=sort)


@router.get(
    "/repositories/{owner}/{repo}",
    response_model=Repository,
    responses={404: {"model": GitHubErrorResponse}},
    summary="Get repository details",
    description="Retrieve metadata for a single GitHub repository.",
)
async def get_repository(
    owner: str,
    repo: str,
    service: GitHubService = Depends(get_github_service),
) -> Repository:
    return await service.get_repository(owner=owner, repo=repo)


# ── Branches & Commits ───────────────────────────────────────────────────────


@router.get(
    "/repositories/{owner}/{repo}/branches",
    response_model=List[Branch],
    responses={404: {"model": GitHubErrorResponse}},
    summary="List repository branches",
    description="Retrieve branch list and head commit SHAs.",
)
async def list_branches(
    owner: str,
    repo: str,
    service: GitHubService = Depends(get_github_service),
) -> List[Branch]:
    return await service.list_branches(owner=owner, repo=repo)


@router.get(
    "/repositories/{owner}/{repo}/commits",
    response_model=List[Commit],
    responses={404: {"model": GitHubErrorResponse}},
    summary="List recent commits",
    description="Retrieve recent git commits for a repository with pagination.",
)
async def list_commits(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    service: GitHubService = Depends(get_github_service),
) -> List[Commit]:
    return await service.list_commits(owner=owner, repo=repo, page=page, per_page=per_page)


# ── GitHub Actions ───────────────────────────────────────────────────────────


@router.get(
    "/repositories/{owner}/{repo}/workflows",
    response_model=List[Workflow],
    responses={404: {"model": GitHubErrorResponse}},
    summary="List Actions workflows",
    description="Retrieve GitHub Actions workflows defined in the repository.",
)
async def list_workflows(
    owner: str,
    repo: str,
    service: GitHubService = Depends(get_github_service),
) -> List[Workflow]:
    return await service.list_workflows(owner=owner, repo=repo)


@router.get(
    "/repositories/{owner}/{repo}/runs",
    response_model=List[WorkflowRun],
    responses={404: {"model": GitHubErrorResponse}},
    summary="List workflow runs",
    description="Retrieve recent workflow runs with optional status or branch filtering.",
)
async def list_workflow_runs(
    owner: str,
    repo: str,
    status: Optional[str] = Query(None, description="Filter by status (e.g. success, failure, completed)"),
    branch: Optional[str] = Query(None, description="Filter by branch name"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    service: GitHubService = Depends(get_github_service),
) -> List[WorkflowRun]:
    return await service.list_workflow_runs(
        owner=owner,
        repo=repo,
        status=status,
        branch=branch,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/repositories/{owner}/{repo}/runs/{run_id}",
    response_model=WorkflowRun,
    responses={404: {"model": GitHubErrorResponse}},
    summary="Get workflow run details",
    description="Retrieve detailed metadata for a single workflow run.",
)
async def get_workflow_run(
    owner: str,
    repo: str,
    run_id: int,
    service: GitHubService = Depends(get_github_service),
) -> WorkflowRun:
    return await service.get_workflow_run(owner=owner, repo=repo, run_id=run_id)


@router.get(
    "/repositories/{owner}/{repo}/runs/{run_id}/jobs",
    response_model=List[WorkflowJob],
    responses={404: {"model": GitHubErrorResponse}},
    summary="List jobs for a workflow run",
    description="Retrieve jobs and steps for a workflow run, highlighting failures for diagnostics.",
)
async def list_workflow_jobs(
    owner: str,
    repo: str,
    run_id: int,
    service: GitHubService = Depends(get_github_service),
) -> List[WorkflowJob]:
    return await service.list_workflow_run_jobs(owner=owner, repo=repo, run_id=run_id)


# ── Logs ─────────────────────────────────────────────────────────────────────


@router.get(
    "/repositories/{owner}/{repo}/runs/{run_id}/logs",
    response_model=WorkflowLogs,
    responses={404: {"model": GitHubErrorResponse}},
    summary="Get workflow run failure logs",
    description="Retrieve diagnostic log snippet for a workflow run (focused on failed jobs).",
)
async def get_workflow_run_logs(
    owner: str,
    repo: str,
    run_id: int,
    max_lines: int = Query(500, ge=50, le=2000, description="Maximum lines to return"),
    service: GitHubService = Depends(get_github_service),
) -> WorkflowLogs:
    return await service.get_workflow_run_logs(
        owner=owner,
        repo=repo,
        run_id=run_id,
        max_lines=max_lines,
    )


@router.get(
    "/repositories/{owner}/{repo}/jobs/{job_id}/logs",
    response_model=WorkflowLogs,
    responses={404: {"model": GitHubErrorResponse}},
    summary="Get job logs",
    description="Retrieve log output for a specific workflow job.",
)
async def get_job_logs(
    owner: str,
    repo: str,
    job_id: int,
    max_lines: int = Query(500, ge=50, le=2000, description="Maximum lines to return"),
    service: GitHubService = Depends(get_github_service),
) -> WorkflowLogs:
    return await service.get_job_logs(
        owner=owner,
        repo=repo,
        job_id=job_id,
        max_lines=max_lines,
    )
