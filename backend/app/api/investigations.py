"""
Investigation API endpoints.

Exposes REST endpoints to trigger AI-powered CI/CD workflow failure investigations
and query historical investigation reports.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.services.investigation.investigation_service import InvestigationService
from app.services.investigation.schemas import (
    InvestigationListItem,
    InvestigationRequest,
    InvestigationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


def get_investigation_service() -> InvestigationService:
    return InvestigationService()


@router.post(
    "",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI investigation for a workflow run",
    description=(
        "Analyzes a GitHub Actions workflow run, extracts failed jobs/steps, "
        "processes console logs, and synthesizes a structured diagnosis via OmniRoute."
    ),
)
async def create_investigation(
    request: InvestigationRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationResponse:
    """Trigger automated root-cause analysis for a workflow run."""
    return await service.investigate_workflow_run(request)


@router.get(
    "",
    response_model=List[InvestigationListItem],
    summary="List investigation history",
    description="Retrieve past investigation summaries, optionally filtered by repository.",
)
async def list_investigations(
    repository: Optional[str] = Query(None, description="Filter by repository name (owner/repo)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    service: InvestigationService = Depends(get_investigation_service),
) -> List[InvestigationListItem]:
    """List historical investigations."""
    return await service.list_investigations(repository=repository, limit=limit)


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Get investigation details",
    description="Retrieve a detailed diagnosis report for a specific investigation ID.",
)
async def get_investigation(
    investigation_id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationResponse:
    """Retrieve full diagnostic report by ID."""
    result = await service.get_investigation(investigation_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation '{investigation_id}' was not found.",
            },
        )
    return result
