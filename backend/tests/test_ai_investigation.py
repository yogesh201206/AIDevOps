"""
Tests for Phase 3: AI Investigation Engine.

Covers:
 1. AI status available
 2. AI status unavailable
 3. Investigation request validation
 4. Successful failed-run investigation (mocked)
 5. Successful workflow should not be treated as failure
 6. Failed job extraction
 7. Failed step extraction
 8. Log processing
 9. Secret redaction
10. Large log truncation
11. Context building
12. OmniRoute timeout
13. OmniRoute unavailable
14. Invalid AI JSON
15. Valid AI JSON
16. Invalid confidence
17. Missing required AI fields
18. GitHub API failure
19. Investigation history
20. Investigation retrieval
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.github.exceptions import GitHubException, GitHubNotFoundError
from app.github.schemas import WorkflowJob, WorkflowLogs, WorkflowRun, WorkflowStep
from app.main import app
from app.services.ai.exceptions import (
    AIParseError,
    AITimeoutError,
    AIUnavailableError,
)
from app.services.ai.omniroute_client import OmniRouteClient
from app.services.ai.parser import AIOutputSchema, parse_ai_response
from app.services.investigation.context_builder import ContextBuilder
from app.services.investigation.log_processor import LogProcessor
from app.services.investigation.schemas import (
    InvestigationRequest,
    InvestigationResponse,
    RootCause,
    SuggestedFix,
)
from app.services.investigation.storage import InvestigationStorage


@pytest.fixture(autouse=True)
def clean_storage():
    """Ensure clean storage before each test."""
    storage = InvestigationStorage.get_instance()
    storage.clear()
    yield
    storage.clear()


@pytest.fixture
def mock_workflow_run():
    return WorkflowRun(
        id=12345,
        workflow_id=987,
        workflow_name="CI Pipeline",
        status="completed",
        conclusion="failure",
        branch="main",
        commit_sha="a1b2c3d4e5f67890",
        commit_short_sha="a1b2c3d",
        commit_message="fix: test commit",
        event="push",
        html_url="https://github.com/test-owner/test-repo/actions/runs/12345",
        run_number=42,
        is_failed=True,
    )


@pytest.fixture
def mock_jobs():
    step1 = WorkflowStep(
        name="Set up Python",
        status="completed",
        conclusion="success",
        number=1,
        is_failed=False,
    )
    step2 = WorkflowStep(
        name="Install dependencies",
        status="completed",
        conclusion="success",
        number=2,
        is_failed=False,
    )
    step3 = WorkflowStep(
        name="Run tests",
        status="completed",
        conclusion="failure",
        number=3,
        started_at="2026-10-08T17:00:00Z",
        completed_at="2026-10-08T17:01:00Z",
        is_failed=True,
    )
    job = WorkflowJob(
        id=555,
        run_id=12345,
        name="Build and Test",
        status="completed",
        conclusion="failure",
        is_failed=True,
        steps=[step1, step2, step3],
        failed_steps=[step3],
    )
    return [job]


@pytest.fixture
def mock_ai_json_output():
    return json.dumps({
        "summary": "The test step failed due to a missing dependency in the test environment.",
        "root_causes": [
            {
                "cause": "Missing dependency",
                "explanation": "ImportError: No module named 'requests' in test_api.py",
                "confidence": 0.92,
            }
        ],
        "evidence": [
            {
                "source": "Run tests",
                "detail": "ModuleNotFoundError: No module named 'requests'",
                "importance": "high",
            }
        ],
        "affected_components": ["Backend unit tests"],
        "severity": "high",
        "suggested_fixes": [
            {
                "description": "Add requests to requirements.txt or test dependencies.",
                "reason": "Resolves ModuleNotFoundError during pytest execution.",
            }
        ],
        "validation_steps": ["Run pytest locally after installing dependencies."],
        "overall_confidence": 0.90,
    })


# ── 1 & 2: AI Status available & unavailable ─────────────────────────────────

@pytest.mark.asyncio
async def test_ai_status_available():
    """Test 1: GET /api/v1/ai/status when OmniRoute is responsive."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch.object(OmniRouteClient, "check_availability", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            response = await client.get("/api/v1/ai/status")
            assert response.status_code == 200
            data = response.json()
            assert data["configured"] is True
            assert data["available"] is True
            assert data["provider"] == "omniroute"
            assert "model" in data


@pytest.mark.asyncio
async def test_ai_status_unavailable():
    """Test 2: GET /api/v1/ai/status when OmniRoute is unreachable."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch.object(OmniRouteClient, "check_availability", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            response = await client.get("/api/v1/ai/status")
            assert response.status_code == 200
            data = response.json()
            assert data["configured"] is True
            assert data["available"] is False
            assert data["provider"] == "omniroute"


# ── 3: Investigation Request Validation ──────────────────────────────────────

@pytest.mark.asyncio
async def test_investigation_request_validation():
    """Test 3: POST /api/v1/investigations with invalid request payloads."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing fields
        res1 = await client.post("/api/v1/investigations", json={})
        assert res1.status_code == 422

        # Invalid run_id (non-positive)
        res2 = await client.post("/api/v1/investigations", json={"owner": "o", "repo": "r", "run_id": -1})
        assert res2.status_code == 422

        # Empty owner string
        res3 = await client.post("/api/v1/investigations", json={"owner": "", "repo": "r", "run_id": 123})
        assert res3.status_code == 422


# ── 4: Successful failed-run investigation ───────────────────────────────────

@pytest.mark.asyncio
async def test_successful_failed_run_investigation(mock_workflow_run, mock_jobs, mock_ai_json_output):
    """Test 4: End-to-end investigation of a failed workflow run."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH, \
             patch("app.services.ai.ai_service.OmniRouteClient.create_chat_completion", new_callable=AsyncMock) as mock_llm:
            
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(return_value=mock_workflow_run)
            gh_inst.list_workflow_run_jobs = AsyncMock(return_value=mock_jobs)
            gh_inst.get_workflow_run_logs = AsyncMock(
                return_value=WorkflowLogs(
                    run_id=12345,
                    job_id=555,
                    available=True,
                    content="FAILED: ModuleNotFoundError: No module named 'requests'",
                    truncated=False,
                )
            )
            mock_llm.return_value = mock_ai_json_output

            response = await client.post(
                "/api/v1/investigations",
                json={"owner": "test-owner", "repo": "test-repo", "run_id": 12345},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["repository"] == "test-owner/test-repo"
            assert data["workflow_run_id"] == 12345
            assert len(data["root_causes"]) == 1
            assert data["root_causes"][0]["cause"] == "Missing dependency"
            assert data["confidence"] == 0.90
            assert len(data["suggested_fixes"]) == 1
            assert data["provider"] == "omniroute"


# ── 5: Successful workflow should not be treated as failure ──────────────────

@pytest.mark.asyncio
async def test_successful_workflow_not_investigated():
    """Test 5: Workflows with conclusion 'success' bypass AI and return clear status."""
    transport = ASGITransport(app=app)
    success_run = WorkflowRun(
        id=99999,
        workflow_id=10,
        workflow_name="Build",
        status="completed",
        conclusion="success",
        branch="main",
        commit_sha="abcd123",
        commit_short_sha="abcd123",
        event="push",
        html_url="https://github.com/test-owner/test-repo/actions/runs/99999",
        is_failed=False,
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH, \
             patch("app.services.ai.ai_service.OmniRouteClient.create_chat_completion", new_callable=AsyncMock) as mock_llm:
            
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(return_value=success_run)

            response = await client.post(
                "/api/v1/investigations",
                json={"owner": "test-owner", "repo": "test-repo", "run_id": 99999},
            )
            assert response.status_code == 200
            data = response.json()
            assert "completed successfully and does not require" in data["summary"]
            assert data["root_causes"] == []
            # Verify AI was NEVER called
            mock_llm.assert_not_called()


# ── 6 & 7: Failed job & step extraction ──────────────────────────────────────

def test_failed_job_and_step_extraction(mock_jobs):
    """Test 6 & 7: Extract failed jobs and failed steps with preceding step context."""
    job = mock_jobs[0]
    assert job.is_failed is True
    assert len(job.failed_steps) == 1
    failed_step = job.failed_steps[0]
    assert failed_step.name == "Run tests"
    assert failed_step.number == 3

    # Check preceding step is step 2
    step_indices = [s.number for s in job.steps]
    failed_idx = step_indices.index(failed_step.number)
    assert failed_idx == 2
    preceding_step = job.steps[failed_idx - 1]
    assert preceding_step.name == "Install dependencies"
    assert preceding_step.is_failed is False


# ── 8: Log processing (error detection & categories) ─────────────────────────

def test_log_processing_error_categorization():
    """Test 8: Identify error lines, warnings, and exit codes."""
    log_text = """
    2026-10-08T17:00:00Z Setting up node environment
    2026-10-08T17:00:01Z npm WARN deprecated querystring@0.2.0: The querystring module is deprecated
    2026-10-08T17:00:02Z npm ERR! code ENOENT
    2026-10-08T17:00:03Z npm ERR! syscall open
    2026-10-08T17:00:04Z Process completed with exit code 1
    """
    analysis = LogProcessor.analyze_log_content(log_text)
    assert len(analysis["error_lines"]) >= 2
    assert any("exit code 1" in e for e in analysis["error_lines"])
    assert len(analysis["warning_lines"]) >= 1


# ── 9: Secret redaction ──────────────────────────────────────────────────────

def test_secret_redaction():
    """Test 9: Redact GitHub tokens, passwords, bearer tokens, and private keys."""
    sensitive_log = """
    Cloning with token: ghp_abcdef1234567890abcdef12345678901234
    Fine grained: github_pat_TEST_TOKEN_REDACTED
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload.sig
    Connecting to postgres://user:supersecretpass123@db.internal:5432/prod
    Using password=my_db_password_456
    """
    redacted = LogProcessor.redact_secrets(sensitive_log)

    assert "ghp_" not in redacted
    assert "TEST_GITHUB_TOKEN_REDACTED" not in redacted
    assert "supersecretpass123" not in redacted
    assert "my_db_password_456" not in redacted
    assert "[REDACTED_SECRET]" in redacted


# ── 10: Large log truncation ─────────────────────────────────────────────────

def test_large_log_truncation():
    """Test 10: Intelligent windowed truncation preserves head, error hot spot, and tail."""
    lines = [f"Setup step line {i}" for i in range(100)]
    lines.append("CRITICAL: Fatal database connection error occurred!")
    for i in range(100):
        lines.append(f"Post-error noisy log line {i}")
    lines.append("Process completed with exit code 1")

    huge_log = "\n".join(lines)
    # Set tight limit
    truncated = LogProcessor.intelligent_truncate(huge_log, max_chars=1000)

    assert len(truncated) <= 1200
    assert "Fatal database connection error occurred!" in truncated
    assert "exit code 1" in truncated
    assert "[... " in truncated and "omitted" in truncated


# ── 11: Context building ─────────────────────────────────────────────────────

def test_context_building(mock_workflow_run, mock_jobs):
    """Test 11: Context builder includes repository, jobs, steps, and logs."""
    builder = ContextBuilder(max_context_chars=10000)
    context = builder.build_context(
        owner="my-org",
        repo="my-app",
        run=mock_workflow_run,
        jobs=mock_jobs,
        logs_content="Error: pytest failed with exit code 1",
    )

    assert "Repository:\nmy-org/my-app" in context
    assert "CI Pipeline" in context
    assert "Build and Test" in context
    assert "Run tests" in context
    assert "Install dependencies" in context
    assert "pytest failed with exit code 1" in context


# ── 12 & 13: OmniRoute Timeout & Unavailable ─────────────────────────────────

@pytest.mark.asyncio
async def test_omniroute_timeout(mock_workflow_run, mock_jobs):
    """Test 12: Handle OmniRoute timeout gracefully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH, \
             patch("app.services.ai.ai_service.OmniRouteClient.create_chat_completion", new_callable=AsyncMock) as mock_llm:
            
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(return_value=mock_workflow_run)
            gh_inst.list_workflow_run_jobs = AsyncMock(return_value=mock_jobs)
            gh_inst.get_workflow_run_logs = AsyncMock(return_value=WorkflowLogs(run_id=1, available=False))
            mock_llm.side_effect = AITimeoutError("AI request timed out during analysis.")

            response = await client.post(
                "/api/v1/investigations",
                json={"owner": "o", "repo": "r", "run_id": 12345},
            )
            assert response.status_code == 504
            data = response.json()
            assert data["detail"]["code"] == "AI_TIMEOUT"


@pytest.mark.asyncio
async def test_omniroute_unavailable(mock_workflow_run, mock_jobs):
    """Test 13: Handle OmniRoute service unavailable gracefully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH, \
             patch("app.services.ai.ai_service.OmniRouteClient.create_chat_completion", new_callable=AsyncMock) as mock_llm:
            
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(return_value=mock_workflow_run)
            gh_inst.list_workflow_run_jobs = AsyncMock(return_value=mock_jobs)
            gh_inst.get_workflow_run_logs = AsyncMock(return_value=WorkflowLogs(run_id=1, available=False))
            mock_llm.side_effect = AIUnavailableError("AI provider is unavailable.")

            response = await client.post(
                "/api/v1/investigations",
                json={"owner": "o", "repo": "r", "run_id": 12345},
            )
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["code"] == "AI_UNAVAILABLE"


# ── 14 & 15: Invalid AI JSON & Valid AI JSON ─────────────────────────────────

def test_invalid_ai_json():
    """Test 14: Safe handling of invalid AI JSON or markdown garbage."""
    with pytest.raises(AIParseError):
        parse_ai_response("I think the pipeline failed because of docker.")

    with pytest.raises(AIParseError):
        parse_ai_response("{ malformed json: missing quotes }")


def test_valid_ai_json_with_markdown(mock_ai_json_output):
    """Test 15: Parse valid AI output wrapped in markdown code fence."""
    wrapped = f"Here is the investigation:\n```json\n{mock_ai_json_output}\n```\nHope this helps!"
    parsed = parse_ai_response(wrapped)
    assert parsed.overall_confidence == 0.90
    assert len(parsed.root_causes) == 1
    assert parsed.root_causes[0].cause == "Missing dependency"


# ── 16: Invalid confidence score ─────────────────────────────────────────────

def test_invalid_confidence_rejected():
    """Test 16: Reject AI output with confidence outside 0.0 to 1.0."""
    bad_data = {
        "summary": "Summary here",
        "root_causes": [{"cause": "C", "explanation": "E", "confidence": 1.5}],
        "overall_confidence": 0.8,
    }
    with pytest.raises(AIParseError):
        parse_ai_response(json.dumps(bad_data))

    bad_overall = {
        "summary": "Summary here",
        "root_causes": [{"cause": "C", "explanation": "E", "confidence": 0.5}],
        "overall_confidence": -0.2,
    }
    with pytest.raises(AIParseError):
        parse_ai_response(json.dumps(bad_overall))


# ── 17: Missing required AI fields ───────────────────────────────────────────

def test_missing_required_ai_fields():
    """Test 17: Reject AI response missing root_causes or summary."""
    incomplete = {
        "summary": "Build failed",
        # missing root_causes
        "overall_confidence": 0.5,
    }
    with pytest.raises(AIParseError):
        parse_ai_response(json.dumps(incomplete))


# ── 18: GitHub API failure ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_github_api_failure_handled():
    """Test 18: Gracefully handle GitHub 404 or API failure during investigation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH:
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(
                side_effect=GitHubNotFoundError("Run not found on GitHub")
            )

            response = await client.post(
                "/api/v1/investigations",
                json={"owner": "o", "repo": "r", "run_id": 999999},
            )
            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["code"] == "GITHUB_NOT_FOUND"


# ── 19 & 20: Investigation History & Retrieval ───────────────────────────────

@pytest.mark.asyncio
async def test_investigation_history_and_retrieval(mock_workflow_run, mock_jobs, mock_ai_json_output):
    """Test 19 & 20: List investigation history and retrieve by investigation_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.investigation.investigation_service.GitHubService") as MockGH, \
             patch("app.services.ai.ai_service.OmniRouteClient.create_chat_completion", new_callable=AsyncMock) as mock_llm:
            
            gh_inst = MockGH.return_value
            gh_inst.get_workflow_run = AsyncMock(return_value=mock_workflow_run)
            gh_inst.list_workflow_run_jobs = AsyncMock(return_value=mock_jobs)
            gh_inst.get_workflow_run_logs = AsyncMock(return_value=WorkflowLogs(run_id=12345, available=False))
            mock_llm.return_value = mock_ai_json_output

            # 1. Trigger investigation
            create_res = await client.post(
                "/api/v1/investigations",
                json={"owner": "test-owner", "repo": "test-repo", "run_id": 12345},
            )
            assert create_res.status_code == 200
            inv_id = create_res.json()["investigation_id"]

            # 2. List investigations
            list_res = await client.get("/api/v1/investigations")
            assert list_res.status_code == 200
            items = list_res.json()
            assert len(items) == 1
            assert items[0]["investigation_id"] == inv_id
            assert items[0]["repository"] == "test-owner/test-repo"

            # Filter by repo
            list_filtered = await client.get("/api/v1/investigations?repository=test-owner/test-repo")
            assert len(list_filtered.json()) == 1

            list_empty = await client.get("/api/v1/investigations?repository=other/repo")
            assert len(list_empty.json()) == 0

            # 3. Retrieve specific investigation
            get_res = await client.get(f"/api/v1/investigations/{inv_id}")
            assert get_res.status_code == 200
            detail = get_res.json()
            assert detail["investigation_id"] == inv_id
            assert detail["severity"] == "high"
            assert detail["confidence"] == 0.90

            # 4. Non-existent ID returns 404
            not_found_res = await client.get("/api/v1/investigations/inv_nonexistent")
            assert not_found_res.status_code == 404
            assert not_found_res.json()["detail"]["code"] == "INVESTIGATION_NOT_FOUND"
