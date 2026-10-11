"""
Unit and integration tests for Docker Intelligence (Phase 4).

Tests Dockerfile static analyzer, build log analyzer, image reference analyzer,
container diagnostics, compose validator, safe CLI executor, API endpoints,
and integration with the AI investigation engine.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.docker import (
    ContainerAnalyzer,
    DockerAnalysisRequest,
    DockerAnalysisResponse,
    DockerCommandForbiddenError,
    DockerComponent,
    DockerComposeAnalyzer,
    DockerfileAnalyzer,
    DockerImageAnalyzer,
    DockerLogAnalyzer,
    DockerService,
    DockerSeverity,
    DockerTimeoutError,
    SafeDockerExecutor,
)
from app.services.investigation.schemas import InvestigationRequest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "docker"


# ── 1. Dockerfile Static Analyzer Tests ────────────────────────────────────────

class TestDockerfileAnalyzer:
    def setup_method(self):
        self.analyzer = DockerfileAnalyzer()

    def test_valid_dockerfile(self):
        content = """
        FROM python:3.11-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt
        COPY . .
        EXPOSE 8000
        CMD ["python", "main.py"]
        """
        findings = self.analyzer.analyze(content)
        # Should not produce critical or high severity errors
        critical_or_high = [f for f in findings if f.severity in {DockerSeverity.CRITICAL, DockerSeverity.HIGH}]
        assert len(critical_or_high) == 0

    def test_missing_dockerfile_none(self):
        findings = self.analyzer.analyze(None)
        assert len(findings) == 1
        assert findings[0].category == "missing_dockerfile"
        assert findings[0].severity == DockerSeverity.CRITICAL

    def test_empty_dockerfile(self):
        findings = self.analyzer.analyze("   \n   \t  ")
        assert len(findings) == 1
        assert findings[0].category == "empty_dockerfile"
        assert findings[0].severity == DockerSeverity.CRITICAL

    def test_mutable_tag_warning(self):
        content = "FROM node:latest\nWORKDIR /app\nCMD [\"node\", \"app.js\"]"
        findings = self.analyzer.analyze(content)
        categories = [f.category for f in findings]
        assert "mutable_tag" in categories

    def test_env_secret_detected(self):
        content = """
        FROM python:3.11-slim
        ENV DATABASE_PASSWORD=supersecretpassword123
        ENV API_TOKEN=ghp_abcdef1234567890
        WORKDIR /app
        CMD ["python", "app.py"]
        """
        findings = self.analyzer.analyze(content)
        secret_findings = [f for f in findings if f.category == "env_secret_baked_in"]
        assert len(secret_findings) >= 1
        assert secret_findings[0].severity == DockerSeverity.HIGH

    def test_missing_from_instruction(self):
        content = "WORKDIR /app\nCOPY . .\nCMD [\"echo\", \"hi\"]"
        findings = self.analyzer.analyze(content)
        categories = [f.category for f in findings]
        assert "missing_from" in categories

    def test_add_instead_of_copy_warning(self):
        content = "FROM alpine:3.18\nADD package.json /app/package.json\nWORKDIR /app\nCMD [\"sh\"]"
        findings = self.analyzer.analyze(content)
        categories = [f.category for f in findings]
        assert "add_instead_of_copy" in categories


# ── 2. Docker Build & Runtime Log Analyzer Tests ──────────────────────────────

class TestDockerLogAnalyzer:
    def setup_method(self):
        self.analyzer = DockerLogAnalyzer()

    def test_manifest_unknown_fixture(self):
        fixture_path = FIXTURES_DIR / "build_log_manifest_unknown.log"
        content = fixture_path.read_text()
        findings = self.analyzer.analyze(content)
        assert len(findings) >= 1
        categories = [f.category for f in findings]
        assert "manifest_unknown" in categories
        match = next(f for f in findings if f.category == "manifest_unknown")
        assert match.severity == DockerSeverity.HIGH
        assert match.component == DockerComponent.IMAGE

    def test_copy_failed_fixture(self):
        fixture_path = FIXTURES_DIR / "build_log_copy_failed.log"
        content = fixture_path.read_text()
        findings = self.analyzer.analyze(content)
        categories = [f.category for f in findings]
        assert "copy_failed" in categories
        match = next(f for f in findings if f.category == "copy_failed")
        assert match.component == DockerComponent.BUILD

    def test_package_install_failure_fixture(self):
        fixture_path = FIXTURES_DIR / "build_log_package_failure.log"
        content = fixture_path.read_text()
        findings = self.analyzer.analyze(content)
        categories = [f.category for f in findings]
        assert "package_install_failure" in categories or "run_command_failed" in categories

    def test_pull_access_denied(self):
        log = "Error response from daemon: pull access denied for private/repo, repository does not exist or may require 'docker login'"
        findings = self.analyzer.analyze(log)
        categories = [f.category for f in findings]
        assert "pull_access_denied" in categories

    def test_out_of_memory_oom(self):
        log = "process did not complete successfully: exit code: 137\nKilled"
        findings = self.analyzer.analyze(log)
        categories = [f.category for f in findings]
        assert "resource_exhaustion" in categories
        match = next(f for f in findings if f.category == "resource_exhaustion")
        assert match.severity == DockerSeverity.CRITICAL

    def test_network_failure(self):
        log = "dial tcp: lookup registry-1.docker.io: no such host"
        findings = self.analyzer.analyze(log)
        categories = [f.category for f in findings]
        assert "network_failure" in categories

    def test_is_docker_related_heuristic(self):
        assert self.analyzer.is_docker_related("Step 1/5 : FROM node:18-alpine") is True
        assert self.analyzer.is_docker_related("ERROR: failed to solve: failed to compute cache key") is True
        assert self.analyzer.is_docker_related("Just running pytest against local python environment") is False


# ── 3. Docker Image Reference Analyzer Tests ─────────────────────────────────

class TestDockerImageAnalyzer:
    def setup_method(self):
        self.analyzer = DockerImageAnalyzer()

    def test_valid_image_reference(self):
        findings = self.analyzer.analyze("python:3.11-slim")
        assert len(findings) == 1
        assert findings[0].category == "valid_image_reference"
        assert findings[0].severity == DockerSeverity.INFO

    def test_missing_tag(self):
        findings = self.analyzer.analyze("redis")
        assert any(f.category == "missing_tag" for f in findings)

    def test_mutable_tag(self):
        findings = self.analyzer.analyze("myrepo/service:latest")
        assert any(f.category == "mutable_tag_used" for f in findings)

    def test_invalid_syntax_uppercase(self):
        findings = self.analyzer.analyze("MyInvalidRepo/App:v1.0")
        assert any(f.category == "uppercase_repository_name" for f in findings)

    def test_missing_image_reference(self):
        findings = self.analyzer.analyze("")
        assert findings[0].category == "missing_image_reference"


# ── 4. Container Diagnostic Analyzer Tests ───────────────────────────────────

class TestContainerAnalyzer:
    def setup_method(self):
        self.analyzer = ContainerAnalyzer()

    def test_container_exit_code_1_fixture(self):
        fixture_path = FIXTURES_DIR / "container_exit_code_1.json"
        data = json.loads(fixture_path.read_text())
        findings = self.analyzer.analyze(data)
        categories = [f.category for f in findings]
        assert "container_non_zero_exit" in categories
        assert "crash_loop_backoff" in categories

    def test_container_port_conflict_fixture(self):
        fixture_path = FIXTURES_DIR / "container_port_conflict.json"
        data = json.loads(fixture_path.read_text())
        findings = self.analyzer.analyze(data)
        categories = [f.category for f in findings]
        assert "port_binding_conflict" in categories

    def test_container_unhealthy(self):
        container_data = {
            "Id": "1234567890ab",
            "Name": "app-health-test",
            "State": {
                "Status": "running",
                "ExitCode": 0,
                "Health": {
                    "Status": "unhealthy",
                    "Log": [{"Output": "curl: (7) Failed to connect to localhost port 8080: Connection refused"}],
                },
            },
        }
        findings = self.analyzer.analyze(container_data)
        categories = [f.category for f in findings]
        assert "container_unhealthy" in categories

    def test_secret_redaction(self):
        env_list = [
            "PORT=8080",
            "API_KEY=ghp_secretkey123",
            "DB_PASSWORD=mysecretpassword",
            "AUTH_TOKEN=jwt_secret",
            "DEBUG=true",
        ]
        redacted = ContainerAnalyzer.redact_env(env_list)
        assert redacted["PORT"] == "8080"
        assert redacted["API_KEY"] == "[REDACTED_SECRET]"
        assert redacted["DB_PASSWORD"] == "[REDACTED_SECRET]"
        assert redacted["AUTH_TOKEN"] == "[REDACTED_SECRET]"
        assert redacted["DEBUG"] == "true"


# ── 5. Docker Compose Static Analyzer Tests ──────────────────────────────────

class TestDockerComposeAnalyzer:
    def setup_method(self):
        self.analyzer = DockerComposeAnalyzer()

    def test_valid_compose(self):
        compose = """
        version: '3.8'
        services:
          web:
            image: nginx:alpine
            ports:
              - "80:80"
          db:
            image: postgres:15-alpine
        """
        findings = self.analyzer.analyze(compose)
        categories = [f.category for f in findings]
        assert "valid_compose_configuration" in categories

    def test_invalid_yaml(self):
        compose = "services:\n  web:\n    image: nginx\n  - malformed: yaml: [["
        findings = self.analyzer.analyze(compose)
        assert findings[0].category == "invalid_compose_yaml"
        assert findings[0].severity == DockerSeverity.CRITICAL

    def test_port_collision_fixture(self):
        fixture_path = FIXTURES_DIR / "compose_port_conflict.yml"
        compose = fixture_path.read_text()
        findings = self.analyzer.analyze(compose)
        categories = [f.category for f in findings]
        assert "compose_port_collision" in categories

    def test_missing_depends_on_fixture(self):
        fixture_path = FIXTURES_DIR / "compose_missing_dep.yml"
        compose = fixture_path.read_text()
        findings = self.analyzer.analyze(compose)
        categories = [f.category for f in findings]
        assert "invalid_depends_on" in categories

    def test_missing_services_block(self):
        compose = "version: '3.8'\nnetworks:\n  frontend:\n"
        findings = self.analyzer.analyze(compose)
        categories = [f.category for f in findings]
        assert "missing_services_block" in categories

    def test_undefined_named_volume(self):
        compose = """
        version: '3.8'
        services:
          db:
            image: postgres:15
            volumes:
              - db_data:/var/lib/postgresql/data
        """
        findings = self.analyzer.analyze(compose)
        categories = [f.category for f in findings]
        assert "undefined_named_volume" in categories


# ── 6. Safe Docker Executor Tests ─────────────────────────────────────────────

class TestSafeDockerExecutor:
    def setup_method(self):
        self.executor = SafeDockerExecutor()

    def test_allowlist_permits_read_only_commands(self):
        tokens = self.executor.sanitize_args("ps", ["-a"])
        assert tokens == ["docker", "ps", "-a"]

        tokens = self.executor.sanitize_args("inspect", ["my-container"])
        assert tokens == ["docker", "inspect", "my-container"]

    def test_forbids_mutating_subcommands(self):
        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("rm", ["container1"])

        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("rmi", ["image1"])

        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("prune")

        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("exec", ["-it", "container1", "sh"])

    def test_forbids_shell_metacharacters(self):
        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("ps", ["container; rm -rf /"])

        with pytest.raises(DockerCommandForbiddenError):
            self.executor.sanitize_args("logs", ["container | grep secret"])

    @pytest.mark.asyncio
    async def test_secret_redaction_in_output(self):
        raw = "Container output: token=ghp_secret_access_key123 and password=super_secret"
        redacted = self.executor.redact_secrets(raw)
        assert "ghp_secret_access_key123" not in redacted
        assert "super_secret" not in redacted


# ── 7. DockerService Core Facade Tests ────────────────────────────────────────

class TestDockerService:
    def setup_method(self):
        self.service = DockerService()

    def test_multi_component_analysis(self):
        request = DockerAnalysisRequest(
            dockerfile_content="FROM node:latest\nWORKDIR /app",
            build_log="ERROR: failed to solve: failed to compute cache key: '/missing.txt' not found",
            image_reference="myrepo/test:latest",
        )
        response = self.service.analyze(request)
        assert isinstance(response, DockerAnalysisResponse)
        assert len(response.evidence) >= 2
        assert "dockerfile" in response.components_analyzed
        assert "build" in response.components_analyzed
        assert "image" in response.components_analyzed
        assert response.highest_severity in {"high", "critical"}
        assert "DOCKER INTELLIGENCE EVIDENCE" in response.context_block
        assert "SOURCE: Docker Build" in response.context_block

    def test_correlate_github_actions_log(self):
        gh_log = """
        2026-10-09T10:00:00Z Step 3: Build Docker image
        #7 ERROR: failed to solve: manifest for python:99.9-nonexistent not found: manifest unknown
        Error: Process completed with exit code 1.
        """
        evidence = self.service.correlate_github_log(gh_log)
        assert len(evidence) >= 1
        assert evidence[0].source == "GitHub Actions (Docker Step)"
        assert evidence[0].category == "manifest_unknown"


# ── 8. Docker API Router Endpoint Tests ───────────────────────────────────────

class TestDockerAPI:
    def setup_method(self):
        self.client = TestClient(app)

    def test_post_docker_analyze_endpoint(self):
        payload = {
            "dockerfile_content": "FROM python:3.11-slim\nWORKDIR /app\nCMD [\"python\"]",
            "build_log": "failed to solve: failed to compute cache key: '/app.py' not found",
        }
        res = self.client.post("/api/v1/docker/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "evidence" in data
        assert "highest_severity" in data
        assert "context_block" in data
        assert len(data["evidence"]) >= 1

    def test_get_docker_status_endpoint(self):
        res = self.client.get("/api/v1/docker/status")
        assert res.status_code == 200
        data = res.json()
        assert "available" in data
        assert "read_only" in data
        assert data["read_only"] is True


# ── 9. Integration with Investigation Pipeline Tests ─────────────────────────

class TestInvestigationDockerIntegration:
    @pytest.mark.asyncio
    async def test_investigation_extracts_docker_evidence_when_present(self):
        from app.services.investigation.investigation_service import InvestigationService
        from app.github.schemas import WorkflowJob, WorkflowRun, WorkflowStep, WorkflowLogs

        # Create mock GitHub service with Docker build failure logs
        mock_gh = MagicMock()
        mock_run = WorkflowRun(
            id=2001,
            workflow_id=10,
            workflow_name="Docker Build & Push",
            status="completed",
            conclusion="failure",
            branch="main",
            commit_sha="abcd1234ef",
            commit_short_sha="abcd123",
            commit_message="Add Dockerfile",
            event="push",
            html_url="https://github.com/org/repo/actions/runs/2001",
            created_at="2026-10-09T10:00:00Z",
            updated_at="2026-10-09T10:01:00Z",
        )
        mock_job = WorkflowJob(
            id=3001,
            run_id=2001,
            name="build-container",
            status="completed",
            conclusion="failure",
            started_at="2026-10-09T10:00:05Z",
            completed_at="2026-10-09T10:00:55Z",
            html_url="https://github.com/org/repo/actions/runs/2001/job/3001",
            steps=[
                WorkflowStep(
                    name="Build Docker image",
                    status="completed",
                    conclusion="failure",
                    number=3,
                )
            ],
        )
        docker_failure_log = """
        [+] Building 0.5s (4/4) FINISHED
        => ERROR [internal] load metadata for docker.io/library/python:99.9-nonexistent 0.4s
        failed to solve: manifest for python:99.9-nonexistent not found: manifest unknown
        """
        mock_logs = WorkflowLogs(
            run_id=2001,
            available=True,
            content=docker_failure_log,
        )

        mock_gh.get_workflow_run = AsyncMock(return_value=mock_run)
        mock_gh.list_workflow_run_jobs = AsyncMock(return_value=[mock_job])
        mock_gh.get_workflow_run_logs = AsyncMock(return_value=mock_logs)

        # Mock AI service
        from app.services.ai.parser import AIOutputSchema
        from app.services.investigation.schemas import RootCause, Evidence, SuggestedFix

        mock_ai = MagicMock()
        mock_ai_output = AIOutputSchema(
            summary="Docker build failed because base image tag does not exist.",
            root_causes=[
                RootCause(
                    cause="Invalid Base Image Tag",
                    explanation="Registry returned manifest unknown for python:99.9-nonexistent.",
                    confidence=0.95,
                )
            ],
            evidence=[
                Evidence(
                    source="GitHub Actions (Docker Step)",
                    detail="manifest for python:99.9-nonexistent not found: manifest unknown",
                    importance="high",
                )
            ],
            affected_components=["Docker Build", "Dockerfile"],
            severity="high",
            suggested_fixes=[
                SuggestedFix(
                    description="Update Dockerfile to use an existing python tag such as 3.11-slim.",
                    reason="python:99.9-nonexistent is not published on Docker Hub.",
                )
            ],
            validation_steps=["Run docker build locally to verify image pulls successfully."],
            overall_confidence=0.95,
        )
        mock_ai.analyze_investigation_context = AsyncMock(return_value=mock_ai_output)

        inv_service = InvestigationService(
            github_service=mock_gh,
            ai_service=mock_ai,
        )

        req = InvestigationRequest(owner="test-org", repo="docker-app", run_id=2001)
        res = await inv_service.investigate_workflow_run(req)

        assert res.status == "completed"
        assert len(res.docker_evidence) >= 1
        assert res.docker_evidence[0].category == "manifest_unknown"

        # Verify that context passed to AI included Docker Intelligence block
        call_args = mock_ai.analyze_investigation_context.call_args
        context_sent = call_args[1].get("context") or call_args[0][0]
        assert "DOCKER INTELLIGENCE EVIDENCE" in context_sent
        assert "manifest_unknown" in context_sent
