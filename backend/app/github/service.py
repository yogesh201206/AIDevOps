"""
GitHub Service layer.

High-level business logic interacting with the GitHub Client.
Normalizes data into application schemas, encapsulates error handling,
and protects against massive log payloads.
"""

import logging
from typing import List, Optional

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAuthenticationError,
    GitHubException,
    GitHubNotFoundError,
    GitHubNotConfiguredError,
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

logger = logging.getLogger(__name__)

# Terminal conclusions considered failures
FAILURE_CONCLUSIONS = {"failure", "timed_out", "startup_failure", "action_required"}


class GitHubService:
    """Business service for GitHub repository and Actions operations."""

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()

    async def get_status(self) -> GitHubStatusResponse:
        """
        Check GitHub connection status.
        Does not raise exceptions; returns a clean status model even if
        unconfigured or authentication fails.
        """
        if not self.client.is_configured:
            return GitHubStatusResponse(
                connected=False,
                reason="GitHub token is not configured",
            )

        try:
            response = await self.client.request(
                method="GET",
                endpoint="/user",
                require_auth=True,
            )
            data = response.json()
            remaining = response.headers.get("x-ratelimit-remaining")
            reset_ts = response.headers.get("x-ratelimit-reset")

            return GitHubStatusResponse(
                connected=True,
                username=data.get("login"),
                avatar_url=data.get("avatar_url"),
                rate_limit_remaining=int(remaining) if remaining is not None else None,
                rate_limit_reset=int(reset_ts) if reset_ts is not None else None,
            )
        except GitHubAuthenticationError:
            return GitHubStatusResponse(
                connected=False,
                reason="GitHub authentication failed: invalid or expired token",
            )
        except GitHubException as exc:
            return GitHubStatusResponse(
                connected=False,
                reason=f"GitHub connection failed: {exc.message}",
            )
        except Exception as exc:
            logger.exception("Unexpected error verifying GitHub status")
            return GitHubStatusResponse(
                connected=False,
                reason=f"GitHub connection error: {str(exc)}",
            )

    async def list_repositories(
        self,
        page: int = 1,
        per_page: int = 30,
        sort: str = "updated",
    ) -> List[Repository]:
        """List repositories accessible to the authenticated user."""
        params = {"page": page, "per_page": min(per_page, 100), "sort": sort}
        raw_repos = await self.client.get_json("/user/repos", params=params)

        repositories = []
        for item in raw_repos:
            owner_login = item.get("owner", {}).get("login", "")
            repositories.append(
                Repository(
                    id=item["id"],
                    name=item["name"],
                    full_name=item["full_name"],
                    owner=owner_login,
                    private=item.get("private", False),
                    html_url=item["html_url"],
                    description=item.get("description"),
                    default_branch=item.get("default_branch", "main"),
                    language=item.get("language"),
                    stars_count=item.get("stargazers_count", 0),
                    forks_count=item.get("forks_count", 0),
                    open_issues_count=item.get("open_issues_count", 0),
                    updated_at=item.get("updated_at"),
                    pushed_at=item.get("pushed_at"),
                )
            )
        return repositories

    async def get_repository(self, owner: str, repo: str) -> Repository:
        """Fetch details for a specific repository."""
        item = await self.client.get_json(f"/repos/{owner}/{repo}")
        owner_login = item.get("owner", {}).get("login", owner)
        return Repository(
            id=item["id"],
            name=item["name"],
            full_name=item["full_name"],
            owner=owner_login,
            private=item.get("private", False),
            html_url=item["html_url"],
            description=item.get("description"),
            default_branch=item.get("default_branch", "main"),
            language=item.get("language"),
            stars_count=item.get("stargazers_count", 0),
            forks_count=item.get("forks_count", 0),
            open_issues_count=item.get("open_issues_count", 0),
            updated_at=item.get("updated_at"),
            pushed_at=item.get("pushed_at"),
        )

    async def list_branches(self, owner: str, repo: str) -> List[Branch]:
        """List branches for a repository."""
        raw_branches = await self.client.get_json(f"/repos/{owner}/{repo}/branches")
        branches = []
        for item in raw_branches:
            branches.append(
                Branch(
                    name=item["name"],
                    commit_sha=item.get("commit", {}).get("sha", ""),
                    protected=item.get("protected", False),
                )
            )
        return branches

    async def list_commits(
        self,
        owner: str,
        repo: str,
        page: int = 1,
        per_page: int = 30,
    ) -> List[Commit]:
        """List recent commits for a repository."""
        params = {"page": page, "per_page": min(per_page, 100)}
        raw_commits = await self.client.get_json(f"/repos/{owner}/{repo}/commits", params=params)

        commits = []
        for item in raw_commits:
            sha = item.get("sha", "")
            commit_data = item.get("commit", {})
            author_data = commit_data.get("author") or {}
            author_login = item.get("author", {}).get("login") if item.get("author") else None
            author_name = author_login or author_data.get("name") or "Unknown"

            raw_message = commit_data.get("message", "")
            first_line = raw_message.split("\n")[0] if raw_message else ""

            commits.append(
                Commit(
                    sha=sha,
                    short_sha=sha[:7] if sha else "",
                    message=first_line,
                    author=author_name,
                    date=author_data.get("date"),
                    url=item.get("html_url", ""),
                )
            )
        return commits

    async def list_workflows(self, owner: str, repo: str) -> List[Workflow]:
        """List GitHub Actions workflows configured in a repository."""
        data = await self.client.get_json(f"/repos/{owner}/{repo}/actions/workflows")
        raw_workflows = data.get("workflows", [])

        workflows = []
        for wf in raw_workflows:
            workflows.append(
                Workflow(
                    id=wf["id"],
                    name=wf.get("name", "Unnamed Workflow"),
                    path=wf.get("path", ""),
                    state=wf.get("state", "active"),
                    html_url=wf.get("html_url"),
                )
            )
        return workflows

    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        status: Optional[str] = None,
        branch: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> List[WorkflowRun]:
        """List recent workflow runs with optional filtering."""
        params = {
            "page": page,
            "per_page": min(per_page, 100),
            "status": status,
            "branch": branch,
        }
        data = await self.client.get_json(f"/repos/{owner}/{repo}/actions/runs", params=params)
        raw_runs = data.get("workflow_runs", [])

        runs = []
        for run in raw_runs:
            head_sha = run.get("head_sha", "")
            conclusion = run.get("conclusion")
            is_failed = conclusion in FAILURE_CONCLUSIONS

            commit_msg = None
            if run.get("head_commit"):
                commit_msg = run["head_commit"].get("message")
                if commit_msg:
                    commit_msg = commit_msg.split("\n")[0]

            runs.append(
                WorkflowRun(
                    id=run["id"],
                    workflow_id=run.get("workflow_id"),
                    workflow_name=run.get("name") or "Workflow",
                    status=run.get("status", "unknown"),
                    conclusion=conclusion,
                    branch=run.get("head_branch") or "unknown",
                    commit_sha=head_sha,
                    commit_short_sha=head_sha[:7] if head_sha else "",
                    commit_message=commit_msg,
                    event=run.get("event", "unknown"),
                    created_at=run.get("created_at"),
                    updated_at=run.get("updated_at"),
                    html_url=run.get("html_url", ""),
                    run_number=run.get("run_number"),
                    run_attempt=run.get("run_attempt"),
                    is_failed=is_failed,
                )
            )
        return runs

    async def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        """Fetch details for a single workflow run."""
        run = await self.client.get_json(f"/repos/{owner}/{repo}/actions/runs/{run_id}")
        head_sha = run.get("head_sha", "")
        conclusion = run.get("conclusion")
        is_failed = conclusion in FAILURE_CONCLUSIONS

        commit_msg = None
        if run.get("head_commit"):
            commit_msg = run["head_commit"].get("message")
            if commit_msg:
                commit_msg = commit_msg.split("\n")[0]

        return WorkflowRun(
            id=run["id"],
            workflow_id=run.get("workflow_id"),
            workflow_name=run.get("name") or "Workflow",
            status=run.get("status", "unknown"),
            conclusion=conclusion,
            branch=run.get("head_branch") or "unknown",
            commit_sha=head_sha,
            commit_short_sha=head_sha[:7] if head_sha else "",
            commit_message=commit_msg,
            event=run.get("event", "unknown"),
            created_at=run.get("created_at"),
            updated_at=run.get("updated_at"),
            html_url=run.get("html_url", ""),
            run_number=run.get("run_number"),
            run_attempt=run.get("run_attempt"),
            is_failed=is_failed,
        )

    async def list_workflow_run_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> List[WorkflowJob]:
        """
        List jobs for a workflow run, identifying failed jobs and failed steps.
        This provides the structural foundation for Phase 3 AI investigation.
        """
        data = await self.client.get_json(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        raw_jobs = data.get("jobs", [])

        jobs = []
        for job in raw_jobs:
            job_conclusion = job.get("conclusion")
            is_job_failed = job_conclusion in FAILURE_CONCLUSIONS

            steps: List[WorkflowStep] = []
            failed_steps: List[WorkflowStep] = []

            for step in job.get("steps", []):
                step_conclusion = step.get("conclusion")
                is_step_failed = step_conclusion in FAILURE_CONCLUSIONS
                ws = WorkflowStep(
                    name=step.get("name", "Step"),
                    status=step.get("status", "unknown"),
                    conclusion=step_conclusion,
                    number=step.get("number", 0),
                    started_at=step.get("started_at"),
                    completed_at=step.get("completed_at"),
                    is_failed=is_step_failed,
                )
                steps.append(ws)
                if is_step_failed:
                    failed_steps.append(ws)

            jobs.append(
                WorkflowJob(
                    id=job["id"],
                    run_id=run_id,
                    name=job.get("name", "Job"),
                    status=job.get("status", "unknown"),
                    conclusion=job_conclusion,
                    started_at=job.get("started_at"),
                    completed_at=job.get("completed_at"),
                    html_url=job.get("html_url"),
                    is_failed=is_job_failed,
                    steps=steps,
                    failed_steps=failed_steps,
                )
            )
        return jobs

    async def get_job_logs(
        self,
        owner: str,
        repo: str,
        job_id: int,
        max_lines: int = 500,
    ) -> WorkflowLogs:
        """
        Retrieve log content for a specific workflow job.
        Truncates oversized outputs to the trailing `max_lines` (where failure logs reside).
        """
        try:
            response = await self.client.get_raw(
                f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",
                accept="application/vnd.github+json",
            )
            raw_text = response.text
            if not raw_text:
                return WorkflowLogs(
                    run_id=0,
                    job_id=job_id,
                    available=False,
                    message="Job log content is empty",
                )

            lines = raw_text.splitlines()
            total_lines = len(lines)
            if total_lines > max_lines:
                # Keep the last max_lines (the failure details)
                selected_lines = lines[-max_lines:]
                content = "\n".join(selected_lines)
                truncated = True
            else:
                content = raw_text
                truncated = False

            return WorkflowLogs(
                run_id=0,
                job_id=job_id,
                available=True,
                content=content,
                truncated=truncated,
                total_lines=total_lines,
            )
        except GitHubNotFoundError:
            return WorkflowLogs(
                run_id=0,
                job_id=job_id,
                available=False,
                message="Job logs not found or log retention expired",
            )
        except GitHubException as exc:
            return WorkflowLogs(
                run_id=0,
                job_id=job_id,
                available=False,
                message=f"Could not retrieve job logs: {exc.message}",
            )

    async def get_workflow_run_logs(
        self,
        owner: str,
        repo: str,
        run_id: int,
        max_lines: int = 500,
    ) -> WorkflowLogs:
        """
        Retrieve logs for a workflow run.
        Prioritizes logs from failed jobs to deliver actionable diagnostic context.
        """
        jobs = await self.list_workflow_run_jobs(owner, repo, run_id)
        if not jobs:
            return WorkflowLogs(
                run_id=run_id,
                available=False,
                message="No jobs found for this workflow run",
            )

        # Prioritize failed jobs
        target_job = next((j for j in jobs if j.is_failed), jobs[0])

        logs = await self.get_job_logs(owner, repo, target_job.id, max_lines=max_lines)
        logs.run_id = run_id
        if logs.available:
            logs.message = f"Displaying logs from job: '{target_job.name}' (ID: {target_job.id})"
        return logs
