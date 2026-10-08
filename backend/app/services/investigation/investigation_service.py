"""
Investigation Service layer.

Coordinates GitHub workflow inspection, log processing, AI analysis through OmniRoute,
and investigation history persistence.
"""

from datetime import datetime, timezone
import logging
import time
from typing import List, Optional
import uuid

from app.config import settings
from app.github.service import GitHubService
from app.services.ai.ai_service import AIService
from app.services.investigation.context_builder import ContextBuilder
from app.services.investigation.schemas import (
    InvestigationListItem,
    InvestigationRequest,
    InvestigationResponse,
    RootCause,
    SuggestedFix,
)
from app.services.investigation.storage import InvestigationStorage

logger = logging.getLogger(__name__)


class InvestigationService:
    """Core orchestration service for AI-powered DevOps failure diagnostics."""

    def __init__(
        self,
        github_service: Optional[GitHubService] = None,
        ai_service: Optional[AIService] = None,
        storage: Optional[InvestigationStorage] = None,
    ):
        self.github = github_service or GitHubService()
        self.ai = ai_service or AIService()
        self.storage = storage or InvestigationStorage.get_instance()
        self.context_builder = ContextBuilder()

    async def investigate_workflow_run(
        self,
        request: InvestigationRequest,
    ) -> InvestigationResponse:
        """
        Execute end-to-end investigation of a GitHub Actions workflow run.
        """
        start_time = time.monotonic()
        owner = request.owner
        repo = request.repo
        run_id = request.run_id
        inv_id = f"inv_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        full_repo_name = f"{owner}/{repo}"

        logger.info(
            "Investigation started | investigation_id=%s repository=%s run_id=%s",
            inv_id,
            full_repo_name,
            run_id,
        )

        # 1. Fetch workflow run details (verifies repository and run existence)
        run = await self.github.get_workflow_run(owner=owner, repo=repo, run_id=run_id)

        # 2. Check run completion status
        if run.conclusion == "success":
            logger.info(
                "Investigation skipped for successful run | run_id=%s conclusion=%s",
                run_id,
                run.conclusion,
            )
            response = InvestigationResponse(
                investigation_id=inv_id,
                repository=full_repo_name,
                workflow_run_id=run.id,
                workflow_name=run.workflow_name,
                status="completed",
                summary="This workflow run completed successfully and does not require failure investigation.",
                root_causes=[],
                evidence=[],
                affected_components=[],
                severity="low",
                confidence=1.0,
                suggested_fixes=[],
                validation_steps=["No action needed; all pipeline jobs and steps succeeded."],
                model=settings.OMNIROUTE_MODEL or "gpt-4o-mini",
                provider="omniroute",
                created_at=now_iso,
            )
            self.storage.save(response)
            return response

        if run.status in {"in_progress", "queued"}:
            logger.info("Investigation deferred for in-progress run | run_id=%s status=%s", run_id, run.status)
            response = InvestigationResponse(
                investigation_id=inv_id,
                repository=full_repo_name,
                workflow_run_id=run.id,
                workflow_name=run.workflow_name,
                status="in_progress",
                summary="This workflow run is currently in progress and has not concluded yet. Failure investigation will be available once the run completes.",
                root_causes=[],
                evidence=[],
                affected_components=[],
                severity="low",
                confidence=1.0,
                suggested_fixes=[],
                validation_steps=["Wait for workflow run execution to complete."],
                model=settings.OMNIROUTE_MODEL or "gpt-4o-mini",
                provider="omniroute",
                created_at=now_iso,
            )
            self.storage.save(response)
            return response

        # 3. Retrieve jobs & identify failed steps
        jobs = await self.github.list_workflow_run_jobs(owner=owner, repo=repo, run_id=run_id)
        failed_jobs = [j for j in jobs if j.is_failed]
        total_failed_steps = sum(len(j.failed_steps) for j in failed_jobs)

        logger.info(
            "Workflow jobs analyzed | run_id=%s failed_jobs=%d failed_steps=%d",
            run_id,
            len(failed_jobs),
            total_failed_steps,
        )

        # 4. Retrieve diagnostic logs
        logs_content: Optional[str] = None
        logs = await self.github.get_workflow_run_logs(
            owner=owner,
            repo=repo,
            run_id=run_id,
            max_lines=1000,
        )
        if logs.available and logs.content:
            logs_content = logs.content

        logger.info(
            "Log retrieval complete | run_id=%s available=%s log_bytes=%d",
            run_id,
            logs.available,
            len(logs_content) if logs_content else 0,
        )

        # 5. Build investigation context
        context = self.context_builder.build_context(
            owner=owner,
            repo=repo,
            run=run,
            jobs=jobs,
            logs_content=logs_content,
        )

        # 6. Send to AI provider via AIService / OmniRoute
        logger.info(
            "AI request started | investigation_id=%s context_len=%d",
            inv_id,
            len(context),
        )

        ai_output = await self.ai.analyze_investigation_context(
            context=context,
            model=settings.OMNIROUTE_MODEL,
        )

        elapsed = time.monotonic() - start_time
        logger.info(
            "Investigation completed | investigation_id=%s duration=%.2fs confidence=%.2f",
            inv_id,
            elapsed,
            ai_output.overall_confidence,
        )

        # 7. Assemble final response model
        response = InvestigationResponse(
            investigation_id=inv_id,
            repository=full_repo_name,
            workflow_run_id=run.id,
            workflow_name=run.workflow_name,
            status="completed",
            summary=ai_output.summary,
            root_causes=ai_output.root_causes,
            evidence=ai_output.evidence,
            affected_components=ai_output.affected_components,
            severity=ai_output.severity,
            confidence=ai_output.overall_confidence,
            suggested_fixes=ai_output.suggested_fixes,
            validation_steps=ai_output.validation_steps,
            model=settings.OMNIROUTE_MODEL or "gpt-4o-mini",
            provider="omniroute",
            created_at=now_iso,
        )

        # 8. Persist to storage
        self.storage.save(response)

        return response

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationResponse]:
        """Retrieve a stored investigation by ID."""
        return self.storage.get(investigation_id)

    async def list_investigations(
        self,
        repository: Optional[str] = None,
        limit: int = 50,
    ) -> List[InvestigationListItem]:
        """List historical investigations."""
        return self.storage.list(repository=repository, limit=limit)
