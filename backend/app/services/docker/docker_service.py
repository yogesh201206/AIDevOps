"""
Docker Intelligence Core Service.

Main orchestration service for Phase 4 Docker intelligence.
Coordinates static Dockerfile analysis, build log parsing, image reference validation,
container diagnostics, and compose file inspection.

Generates structured DockerEvidence and AI-ready context blocks.
Safe read-only design guarantees no mutating actions are taken on the host or containers.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.docker.compose_analyzer import DockerComposeAnalyzer
from app.services.docker.container_analyzer import ContainerAnalyzer
from app.services.docker.dockerfile_analyzer import DockerfileAnalyzer
from app.services.docker.image_analyzer import DockerImageAnalyzer
from app.services.docker.log_analyzer import DockerLogAnalyzer
from app.services.docker.safe_executor import SafeDockerExecutor
from app.services.docker.schemas import (
    DockerAnalysisRequest,
    DockerAnalysisResponse,
    DockerComponent,
    DockerEvidence,
    DockerSeverity,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    DockerSeverity.INFO: 0,
    DockerSeverity.LOW: 1,
    DockerSeverity.MEDIUM: 2,
    DockerSeverity.HIGH: 3,
    DockerSeverity.CRITICAL: 4,
}


class DockerService:
    """Facade service orchestrating all Docker intelligence capabilities."""

    def __init__(
        self,
        dockerfile_analyzer: Optional[DockerfileAnalyzer] = None,
        log_analyzer: Optional[DockerLogAnalyzer] = None,
        image_analyzer: Optional[DockerImageAnalyzer] = None,
        container_analyzer: Optional[ContainerAnalyzer] = None,
        compose_analyzer: Optional[DockerComposeAnalyzer] = None,
        safe_executor: Optional[SafeDockerExecutor] = None,
    ):
        self.dockerfile_analyzer = dockerfile_analyzer or DockerfileAnalyzer()
        self.log_analyzer = log_analyzer or DockerLogAnalyzer()
        self.image_analyzer = image_analyzer or DockerImageAnalyzer()
        self.container_analyzer = container_analyzer or ContainerAnalyzer()
        self.compose_analyzer = compose_analyzer or DockerComposeAnalyzer()
        self.safe_executor = safe_executor or SafeDockerExecutor()

    def analyze(self, request: DockerAnalysisRequest) -> DockerAnalysisResponse:
        """
        Execute comprehensive Docker analysis on the provided artifacts.
        """
        all_evidence: List[DockerEvidence] = []
        components_analyzed: List[str] = []

        # 1. Analyze Dockerfile content
        if request.dockerfile_content is not None:
            components_analyzed.append("dockerfile")
            df_findings = self.dockerfile_analyzer.analyze(request.dockerfile_content)
            all_evidence.extend(df_findings)

        # 2. Analyze Docker build logs
        if request.build_log:
            components_analyzed.append("build")
            build_findings = self.log_analyzer.analyze(request.build_log)
            all_evidence.extend(build_findings)

        # 3. Analyze Docker image reference
        if request.image_reference:
            components_analyzed.append("image")
            img_findings = self.image_analyzer.analyze(request.image_reference)
            all_evidence.extend(img_findings)

        # 4. Analyze Container diagnostic data
        if request.container_info or request.container_logs:
            components_analyzed.append("container")
            cnt_findings = self.container_analyzer.analyze(
                container_info=request.container_info,
                container_logs=request.container_logs,
            )
            all_evidence.extend(cnt_findings)

        # 5. Analyze Docker Compose file
        if request.compose_content is not None:
            components_analyzed.append("compose")
            cmp_findings = self.compose_analyzer.analyze(request.compose_content)
            all_evidence.extend(cmp_findings)

        # 6. Correlate with GitHub Actions logs if provided
        if request.github_actions_log:
            gh_docker_findings = self.correlate_github_log(request.github_actions_log)
            if gh_docker_findings:
                if "github_actions" not in components_analyzed:
                    components_analyzed.append("github_actions")
                all_evidence.extend(gh_docker_findings)

        # Calculate highest severity
        highest_sev = DockerSeverity.INFO
        for ev in all_evidence:
            if SEVERITY_ORDER.get(ev.severity, 0) > SEVERITY_ORDER.get(highest_sev, 0):
                highest_sev = ev.severity

        # Generate summary
        summary = self._generate_summary(all_evidence, components_analyzed)

        # Generate context block for AI prompt
        context_block = self.build_context_block(all_evidence)

        return DockerAnalysisResponse(
            evidence=all_evidence,
            summary=summary,
            highest_severity=highest_sev.value,
            components_analyzed=components_analyzed,
            context_block=context_block,
        )

    def correlate_github_log(self, github_log: str) -> List[DockerEvidence]:
        """
        Scan GitHub Actions workflow logs for embedded Docker commands or errors.
        """
        if not github_log or not github_log.strip():
            return []

        findings = self.log_analyzer.analyze(github_log)
        # Re-tag source to show correlation
        for f in findings:
            f.source = "GitHub Actions (Docker Step)"
        return findings

    def build_context_block(self, evidence: List[DockerEvidence]) -> str:
        """
        Formats structured Docker evidence for injection into the AI investigation context.
        """
        if not evidence:
            return ""

        lines = [
            "==================================================",
            "DOCKER INTELLIGENCE EVIDENCE (PHASE 4)",
            "==================================================",
        ]

        # Group evidence by component
        by_comp: Dict[str, List[DockerEvidence]] = {}
        for ev in evidence:
            by_comp.setdefault(ev.component.value, []).append(ev)

        for comp, items in by_comp.items():
            lines.append(f"\n[DOCKER COMPONENT: {comp.upper()}]")
            for item in items:
                lines.append(f"- SOURCE: {item.source}")
                lines.append(f"  CATEGORY: {item.category}")
                lines.append(f"  SEVERITY: {item.severity.value.upper()} (Confidence: {item.confidence:.2f})")
                lines.append(f"  MESSAGE: {item.message}")
                lines.append("  EVIDENCE SNIPPET:")
                for ev_line in item.evidence.splitlines():
                    lines.append(f"    {ev_line}")
                lines.append("")

        lines.append("==================================================")
        return "\n".join(lines)

    def _generate_summary(
        self,
        evidence: List[DockerEvidence],
        components_analyzed: List[str],
    ) -> str:
        if not evidence:
            return f"Docker analysis completed across components ({', '.join(components_analyzed) or 'none'}); no issues detected."

        critical_or_high = [
            e for e in evidence if e.severity in {DockerSeverity.CRITICAL, DockerSeverity.HIGH}
        ]
        if critical_or_high:
            top_issue = critical_or_high[0]
            return (
                f"Docker intelligence detected {len(critical_or_high)} critical/high-severity issue(s). "
                f"Primary finding in '{top_issue.component.value}': {top_issue.message}"
            )

        return f"Docker intelligence found {len(evidence)} observation(s) across {len(components_analyzed)} component(s)."

    async def check_daemon_status(self) -> Dict[str, Any]:
        """
        Safely check if the host Docker daemon is available and read-only version info.
        """
        try:
            version_output = await self.safe_executor.execute("version", ["--format", "{{json .}}"])
            return {
                "available": True,
                "version_info": version_output,
                "read_only": True,
            }
        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
                "read_only": True,
            }
