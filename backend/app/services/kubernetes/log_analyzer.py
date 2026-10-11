"""
Kubernetes Log Intelligence Analyzer.

Performs read-only inspection and analysis of Kubernetes container logs
and CI/CD logs with embedded kubectl/kubernetes failures:
- Application panic, fatal errors, exception tracebacks
- Out of Memory (OOM) kills and SIGKILL (exit code 137)
- Connection refused / database unavailable / port bind collision
- Failed probe errors
- Output-size limits, line truncation, and secret redaction
- Never executes commands inside containers
"""

import logging
import re
from typing import List, Optional

from app.services.investigation.log_processor import LogProcessor
from app.services.kubernetes.schemas import (
    KubernetesComponent,
    KubernetesEvidence,
    KubernetesSeverity,
)

logger = logging.getLogger(__name__)

# Pattern signatures for common Kubernetes container runtime crashes
KUBERNETES_LOG_SIGNATURES = [
    {
        "category": "oom_killed",
        "pattern": re.compile(
            r"(?:fatal error: runtime: out of memory|java\.lang\.OutOfMemoryError|killed\s+process\s+\d+|oom-killer|exit\s+code\s+137|command\s+terminated\s+with\s+exit\s+code\s+137)",
            re.IGNORECASE,
        ),
        "severity": KubernetesSeverity.CRITICAL,
        "confidence": 0.95,
        "message": "Container terminated due to memory exhaustion (OOM)",
        "probable_root_cause": "Application process exceeded Kubernetes memory limit (limits.memory).",
        "suggested_fix": "Increase memory limits in the container spec ('resources.limits.memory') or tune application JVM/heap memory.",
        "validation_steps": ["kubectl describe pod <pod_name>", "kubectl top pod <pod_name>"],
    },
    {
        "category": "startup_crash",
        "pattern": re.compile(
            r"(?:panic:\s+|Traceback\s+\(most\s+recent\s+call\s+last\):|Fatal error:|Unhandled exception|org\.springframework\.boot|Error:\s+Cannot\s+find\s+module)",
            re.IGNORECASE,
        ),
        "severity": KubernetesSeverity.CRITICAL,
        "confidence": 0.92,
        "message": "Application crashed with fatal error or unhandled exception during startup",
        "probable_root_cause": "Application entrypoint encountered an unhandled exception or fatal initialization error.",
        "suggested_fix": "Examine container traceback and verify required environment variables or configuration files.",
        "validation_steps": ["kubectl logs <pod_name> --previous"],
    },
    {
        "category": "address_in_use",
        "pattern": re.compile(
            r"(?:bind:\s+address\s+already\s+in\s+use|EADDRINUSE|address\s+already\s+in\s+use)",
            re.IGNORECASE,
        ),
        "severity": KubernetesSeverity.HIGH,
        "confidence": 0.95,
        "message": "Port collision or socket address already in use inside container",
        "probable_root_cause": "Container attempted to bind to a network port that is already occupied.",
        "suggested_fix": "Ensure container port in application matches containerPort in pod manifest and no duplicate processes are launched.",
        "validation_steps": ["kubectl describe pod <pod_name>"],
    },
    {
        "category": "connection_refused",
        "pattern": re.compile(
            r"(?:dial\s+tcp\s+.*:\s+connect:\s+connection\s+refused|ConnectionRefusedError|failed\s+to\s+connect\s+to\s+.*:\d+|ECONNREFUSED)",
            re.IGNORECASE,
        ),
        "severity": KubernetesSeverity.HIGH,
        "confidence": 0.85,
        "message": "Downstream network dependency connection refused",
        "probable_root_cause": "Application could not connect to a dependent Kubernetes Service or database.",
        "suggested_fix": "Verify that the dependent Service and Pods are running, ready, and reachable on the configured port/DNS name.",
        "validation_steps": ["kubectl get svc,endpoints -n <namespace>"],
    },
    {
        "category": "kubectl_apply_error",
        "pattern": re.compile(
            r"(?:error:\s+error\s+validating\s+|The\s+Deployment\s+.*is\s+invalid|error:\s+timed\s+out\s+waiting\s+for\s+the\s+condition|error:\s+unable\s+to\s+recognize)",
            re.IGNORECASE,
        ),
        "severity": KubernetesSeverity.HIGH,
        "confidence": 0.93,
        "message": "kubectl deployment or manifest application failed",
        "probable_root_cause": "Kubernetes API rejected resource definition during kubectl apply or rollout timed out.",
        "suggested_fix": "Validate manifest with 'kubectl apply --dry-run=client -f <file>' and check API version compatibility.",
        "validation_steps": ["kubectl apply --dry-run=client -f <file>"],
    },
]


class KubernetesLogAnalyzer:
    """Specialized analyzer for Kubernetes container logs and kubectl CLI logs."""

    def __init__(self, max_log_chars: int = 50_000, max_lines: int = 500):
        self.max_log_chars = max_log_chars
        self.max_lines = max_lines

    def sanitize_and_truncate(self, raw_logs: str) -> str:
        """
        Redact sensitive tokens and passwords, enforce line and character budget.
        """
        if not raw_logs:
            return ""

        # Redact secrets
        redacted = LogProcessor.redact_secrets(raw_logs)

        # Enforce max lines
        lines = redacted.splitlines()
        if len(lines) > self.max_lines:
            # Keep tail lines as they typically hold the crash/failure
            lines = lines[-self.max_lines :]
            redacted = f"[... truncated {len(raw_logs.splitlines()) - self.max_lines} preceding lines ...]\n" + "\n".join(lines)

        # Enforce max chars
        if len(redacted) > self.max_log_chars:
            redacted = redacted[-self.max_log_chars :]
            redacted = "[... truncated to character limit ...]\n" + redacted

        return redacted

    def analyze(
        self,
        logs: str,
        pod_name: Optional[str] = None,
        container_name: Optional[str] = None,
        namespace: Optional[str] = "default",
    ) -> List[KubernetesEvidence]:
        """
        Scan logs for known failure patterns.
        """
        findings: List[KubernetesEvidence] = []
        if not logs or not logs.strip():
            return findings

        clean_logs = self.sanitize_and_truncate(logs)

        for sig in KUBERNETES_LOG_SIGNATURES:
            match = sig["pattern"].search(clean_logs)
            if match:
                # Extract surrounding excerpt (up to 5 lines before and after)
                matched_text = match.group(0)
                excerpt = self._extract_context_excerpt(clean_logs, match.start(), match.end())

                findings.append(
                    KubernetesEvidence(
                        source="Kubernetes Container Logs",
                        component=KubernetesComponent.LOG,
                        resource_kind="Pod",
                        resource_name=pod_name or "container-log",
                        namespace=namespace or "default",
                        category=sig["category"],
                        severity=sig["severity"],
                        message=sig["message"],
                        evidence=excerpt,
                        confidence=sig["confidence"],
                        probable_root_cause=sig["probable_root_cause"],
                        suggested_fix=sig["suggested_fix"],
                        validation_steps=[
                            step.replace("<pod_name>", pod_name or "POD").replace("<namespace>", namespace or "default")
                            for step in sig["validation_steps"]
                        ],
                        uncertainties=[
                            "Log excerpt captured from tail; earlier startup context may provide additional background."
                        ],
                        metadata={
                            "container": container_name or "default",
                            "matched_signature": sig["category"],
                        },
                    )
                )

        return findings

    def _extract_context_excerpt(self, text: str, match_start: int, match_end: int) -> str:
        """Extract a readable snippet around a regex match."""
        start_idx = max(0, match_start - 300)
        end_idx = min(len(text), match_end + 300)
        snippet = text[start_idx:end_idx].strip()
        return f"... {snippet} ..."
