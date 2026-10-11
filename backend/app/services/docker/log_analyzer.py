"""
Docker Log Analyzer.

Parses and normalizes Docker build logs, container logs, and daemon output
into structured DockerEvidence records. Detects common build, pull, network,
runtime, and dependency errors without requiring a live Docker daemon.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.docker.schemas import (
    DockerComponent,
    DockerEvidence,
    DockerSeverity,
)

logger = logging.getLogger(__name__)


# ── Common Docker Build & Runtime Failure Signatures ───────────────────────────

DOCKER_LOG_PATTERNS = [
    # 1. Pull Access Denied / Authentication
    {
        "category": "pull_access_denied",
        "pattern": re.compile(
            r"(?:pull access denied for ([^\s,]+)|repository does not exist or may require 'docker login'|"
            r"unauthorized: authentication required|authentication failed|denied: requested access to the resource is denied)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.IMAGE,
        "message": "Docker image pull denied or repository requires authentication.",
        "confidence": 0.95,
    },
    # 2. Manifest Unknown / Image Not Found
    {
        "category": "manifest_unknown",
        "pattern": re.compile(
            r"(?:manifest for ([^\s]+) not found|manifest unknown|image not found|not found: manifest unknown|"
            r"no matching manifest for (?:[^\s]+) in the manifest list entries)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.IMAGE,
        "message": "Docker image or specific image tag not found in registry.",
        "confidence": 0.95,
    },
    # 3. Architecture / Platform Mismatch
    {
        "category": "architecture_mismatch",
        "pattern": re.compile(
            r"(?:no matching manifest for linux\/[^\s]+|exec format error|standard_init_linux\.go:\d+: exec user process caused: exec format error)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.IMAGE,
        "message": "CPU architecture or platform mismatch (e.g. linux/arm64 vs linux/amd64).",
        "confidence": 0.90,
    },
    # 4. BuildKit "failed to solve"
    {
        "category": "failed_to_solve",
        "pattern": re.compile(
            r"(?:ERROR: failed to solve:? (.+)|failed to solve with frontend dockerfile\.v0:? (.+))",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.BUILD,
        "message": "Docker BuildKit solver failed to complete the build graph.",
        "confidence": 0.90,
    },
    # 5. COPY Failed / Missing Context Source
    {
        "category": "copy_failed",
        "pattern": re.compile(
            r"(?:failed to compute cache key:? [\"']?([^\s\"']+)[\"']? not found|COPY failed: (?:file not found in build context|stat [^:]+: no such file or directory)|"
            r"cannot copy to non-directory|failed to calculate checksum of ref [^:]+: \"[^\"]+\": not found)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.BUILD,
        "message": "COPY instruction failed because the source file or directory does not exist in the build context.",
        "confidence": 0.95,
    },
    # 6. RUN Command Exit Code / Failure
    {
        "category": "run_command_failed",
        "pattern": re.compile(
            r"(?:The command ['\"]?([^'\"\n]+)['\"]? returned a non-zero code:\s*(\d+)|"
            r"process ['\"]?([^'\"\n]+)['\"]? did not complete successfully: exit code:\s*(\d+)|"
            r"executor failed running \[([^\]]+)\]: exit code:\s*(\d+))",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.BUILD,
        "message": "RUN instruction command failed with a non-zero exit code during image build.",
        "confidence": 0.90,
    },
    # 7. Package Installation Failure (apt / apk / pip / npm / yarn)
    {
        "category": "package_install_failure",
        "pattern": re.compile(
            r"(?:E: Unable to locate package ([^\s\n]+)|npm ERR! code ([A-Z0-9_]+)|"
            r"pip install.*returned non-zero|ERROR: No matching distribution found for ([^\s\n]+)|"
            r"apk update.*fetch failed|yarn error ([^\n]+)|Could not find a version that satisfies the requirement)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.BUILD,
        "message": "Dependency or package installation failed during build.",
        "confidence": 0.88,
    },
    # 8. Permission Denied
    {
        "category": "permission_denied",
        "pattern": re.compile(
            r"(?:permission denied|EACCES: permission denied|Operation not permitted|chmod: cannot change permissions)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.BUILD,
        "message": "File or socket permission denied during build or container execution.",
        "confidence": 0.85,
    },
    # 9. Network Failure
    {
        "category": "network_failure",
        "pattern": re.compile(
            r"(?:dial tcp: lookup [^\s]+: no such host|Could not resolve host|Failed to connect to [^\s]+|Connection timed out|"
            r"ETIMEDOUT|ECONNREFUSED|ENOTFOUND|temporary failure in name resolution)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.MEDIUM,
        "component": DockerComponent.BUILD,
        "message": "Network resolution or connection failure during Docker build or execution.",
        "confidence": 0.85,
    },
    # 10. Out of Memory / Disk Space
    {
        "category": "resource_exhaustion",
        "pattern": re.compile(
            r"(?:no space left on device|out of memory|fatal error: runtime: out of memory|Killed\s*$|oom-killer|exit code:\s*137)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.CRITICAL,
        "component": DockerComponent.RUNTIME,
        "message": "Container or build failed due to resource exhaustion (out of memory or disk full).",
        "confidence": 0.95,
    },
    # 11. Port Conflict
    {
        "category": "port_binding_conflict",
        "pattern": re.compile(
            r"(?:bind: address already in use|port is already allocated|listen tcp [^\s]+: bind: address already in use|failed to bind to port \d+)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.CONTAINER,
        "message": "Port binding conflict: host port is already allocated by another process.",
        "confidence": 0.95,
    },
    # 12. Dockerfile Parse / Syntax Error
    {
        "category": "dockerfile_parse_error",
        "pattern": re.compile(
            r"(?:dockerfile parse error line \d+:|unknown instruction: ([^\s]+)|syntax error in Dockerfile)",
            re.IGNORECASE,
        ),
        "severity": DockerSeverity.HIGH,
        "component": DockerComponent.DOCKERFILE,
        "message": "Dockerfile syntax error encountered by the builder.",
        "confidence": 0.95,
    },
]


class DockerLogAnalyzer:
    """Analyzer for Docker build, runtime, and container log streams."""

    def analyze(self, log_content: Optional[str]) -> List[DockerEvidence]:
        """
        Scan log content for known Docker failure patterns and produce structured evidence.
        """
        if not log_content or not log_content.strip():
            return []

        findings: List[DockerEvidence] = []
        seen_categories = set()

        lines = log_content.splitlines()

        for idx, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            for pattern_def in DOCKER_LOG_PATTERNS:
                cat = pattern_def["category"]
                if cat in seen_categories:
                    continue  # Deduplicate same category to keep findings clear

                match = pattern_def["pattern"].search(stripped_line)
                if match:
                    seen_categories.add(cat)

                    # Extract context window (up to 3 preceding and 3 following lines)
                    start_idx = max(0, idx - 2)
                    end_idx = min(len(lines), idx + 3)
                    context_snippet = "\n".join(lines[start_idx:end_idx]).strip()

                    findings.append(
                        DockerEvidence(
                            source="Docker Build",
                            component=pattern_def["component"],
                            category=cat,
                            severity=pattern_def["severity"],
                            message=pattern_def["message"],
                            evidence=context_snippet or stripped_line,
                            confidence=pattern_def["confidence"],
                            metadata={
                                "line_number": idx + 1,
                                "matched_line": stripped_line,
                            },
                        )
                    )

        logger.debug("DockerLogAnalyzer completed | findings=%d", len(findings))
        return findings

    def is_docker_related(self, text: str) -> bool:
        """
        Heuristic check to determine if a log stream contains Docker-related operations.
        """
        if not text:
            return False
        keywords = [
            "docker", "buildkit", "dockerfile", "container", "docker-compose",
            "docker compose", "step 1/", "failed to solve", "daemon", "docker.sock",
            "pulling from", "digest: sha256:", "entrypoint", "workdir"
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)
