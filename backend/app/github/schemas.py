"""
GitHub Pydantic schemas.

Domain models for all GitHub REST API data returned by the backend.
Transforms raw GitHub responses into clean, normalized application models.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GitHubErrorDetail(BaseModel):
    """Detailed error object returned on GitHub operations."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of error")


class GitHubErrorResponse(BaseModel):
    """Standardized error envelope for GitHub-related failures."""

    detail: GitHubErrorDetail


class GitHubStatusResponse(BaseModel):
    """GitHub connection health status."""

    model_config = ConfigDict(from_attributes=True)

    connected: bool = Field(..., description="Whether GitHub credentials and connection are valid")
    username: Optional[str] = Field(None, description="Authenticated GitHub user login")
    reason: Optional[str] = Field(None, description="Explanation when not connected")
    rate_limit_remaining: Optional[int] = Field(None, description="Remaining API requests in window")
    rate_limit_reset: Optional[int] = Field(None, description="Unix timestamp of rate limit reset")
    avatar_url: Optional[str] = Field(None, description="GitHub user avatar image URL")


class Repository(BaseModel):
    """Normalized repository metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="GitHub repository ID")
    name: str = Field(..., description="Repository short name")
    full_name: str = Field(..., description="Full repository path (owner/repo)")
    owner: str = Field(..., description="Repository owner login")
    private: bool = Field(..., description="Whether repository is private")
    html_url: str = Field(..., description="GitHub web URL")
    description: Optional[str] = Field(None, description="Repository description")
    default_branch: str = Field("main", description="Default branch name")
    language: Optional[str] = Field(None, description="Primary programming language")
    stars_count: int = Field(0, description="Stargazer count")
    forks_count: int = Field(0, description="Forks count")
    open_issues_count: int = Field(0, description="Open issues and PRs count")
    updated_at: Optional[str] = Field(None, description="ISO timestamp of last update")
    pushed_at: Optional[str] = Field(None, description="ISO timestamp of last commit push")


class Branch(BaseModel):
    """Normalized branch information."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Branch name")
    commit_sha: str = Field(..., description="HEAD commit SHA")
    protected: bool = Field(False, description="Whether branch has branch protection enabled")


class Commit(BaseModel):
    """Normalized commit information."""

    model_config = ConfigDict(from_attributes=True)

    sha: str = Field(..., description="Full git commit SHA")
    short_sha: str = Field(..., description="Short git commit SHA (7 chars)")
    message: str = Field(..., description="Commit message header/body")
    author: str = Field(..., description="Commit author name or login")
    date: Optional[str] = Field(None, description="ISO timestamp of commit")
    url: str = Field(..., description="GitHub web URL for commit")


class Workflow(BaseModel):
    """GitHub Actions workflow definition."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Workflow ID")
    name: str = Field(..., description="Workflow display name")
    path: str = Field(..., description="Path to workflow file (.github/workflows/...)")
    state: str = Field(..., description="Workflow state (active, disabled_manually, etc.)")
    html_url: Optional[str] = Field(None, description="GitHub web URL for workflow")


class WorkflowStep(BaseModel):
    """Individual step within a workflow job."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Step name")
    status: str = Field(..., description="Step execution status (completed, in_progress, queued)")
    conclusion: Optional[str] = Field(None, description="Step conclusion (success, failure, skipped)")
    number: int = Field(..., description="Step order number")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    is_failed: bool = Field(False, description="True if step concluded with failure/error")


class WorkflowJob(BaseModel):
    """Job within a workflow run."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Job ID")
    run_id: int = Field(..., description="Parent workflow run ID")
    name: str = Field(..., description="Job name")
    status: str = Field(..., description="Job status (completed, in_progress, queued)")
    conclusion: Optional[str] = Field(None, description="Job conclusion (success, failure, cancelled)")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    html_url: Optional[str] = Field(None, description="GitHub web URL for job")
    is_failed: bool = Field(False, description="True if job concluded with failure")
    steps: List[WorkflowStep] = Field(default_factory=list, description="All steps executed")
    failed_steps: List[WorkflowStep] = Field(default_factory=list, description="Steps that failed")


class WorkflowRun(BaseModel):
    """GitHub Actions workflow run."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Workflow run ID")
    workflow_id: Optional[int] = Field(None, description="Associated workflow ID")
    workflow_name: str = Field(..., description="Workflow display name")
    status: str = Field(..., description="Run status (completed, in_progress, queued)")
    conclusion: Optional[str] = Field(None, description="Run conclusion (success, failure, timed_out, cancelled)")
    branch: str = Field(..., description="Target git branch (head_branch)")
    commit_sha: str = Field(..., description="Target git commit SHA (head_sha)")
    commit_short_sha: str = Field(..., description="Target git commit short SHA")
    commit_message: Optional[str] = Field(None, description="Commit message")
    event: str = Field(..., description="Triggering event (push, pull_request, workflow_dispatch)")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    html_url: str = Field(..., description="GitHub web URL for run")
    run_number: Optional[int] = Field(None, description="Run increment number")
    run_attempt: Optional[int] = Field(None, description="Attempt number")
    is_failed: bool = Field(False, description="True if run ended in failure/timed_out")


class WorkflowLogs(BaseModel):
    """Workflow or job log summary."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int = Field(..., description="Workflow run ID")
    job_id: Optional[int] = Field(None, description="Specific job ID if logs are for a job")
    available: bool = Field(..., description="Whether logs could be retrieved")
    content: Optional[str] = Field(None, description="Log output (truncated if oversized)")
    truncated: bool = Field(False, description="Whether log was truncated to limit size")
    total_lines: Optional[int] = Field(None, description="Total number of lines in raw log")
    message: Optional[str] = Field(None, description="Status/explanation note")
