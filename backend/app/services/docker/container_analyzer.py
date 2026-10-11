"""
Container Diagnostic Analyzer.

Evaluates container inspection dictionaries (from docker inspect or API),
identifies crash loops, non-zero exits, healthcheck failures, port binding conflicts,
and ensures strict redaction of sensitive environment variables and credentials.
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

# Secret key pattern for redaction
SECRET_KEY_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|credential|auth[_-]?key|auth[_-]?token)",
    re.IGNORECASE,
)

# Known Linux/Docker exit code meanings
EXIT_CODE_MAP = {
    0: "Success (Clean exit)",
    1: "Application error or general runtime exception",
    2: "Misuse of shell builtins",
    126: "Command invoked cannot execute (Permission denied or not executable)",
    127: "Command not found (Binary or script does not exist in container)",
    128: "Invalid exit argument",
    130: "Container terminated by Ctrl+C (SIGINT)",
    137: "Container killed by Out-Of-Memory (OOM) killer or SIGKILL",
    139: "Segmentation fault (SIGSEGV)",
    143: "Container gracefully terminated by SIGTERM",
}


class ContainerAnalyzer:
    """Analyzer for Docker container status, metadata, and runtime diagnostics."""

    @staticmethod
    def redact_env(env_list_or_dict: Any) -> Dict[str, str]:
        """
        Redact sensitive values from environment variables.
        Accepts either a dict {"KEY": "VAL"} or list of strings ["KEY=VAL"].
        """
        redacted: Dict[str, str] = {}

        if isinstance(env_list_or_dict, list):
            for item in env_list_or_dict:
                if "=" in item:
                    k, v = item.split("=", 1)
                    if SECRET_KEY_PATTERN.search(k):
                        redacted[k] = "[REDACTED_SECRET]"
                    else:
                        redacted[k] = v
                else:
                    redacted[item] = ""
        elif isinstance(env_list_or_dict, dict):
            for k, v in env_list_or_dict.items():
                if SECRET_KEY_PATTERN.search(k):
                    redacted[k] = "[REDACTED_SECRET]"
                else:
                    redacted[k] = str(v)

        return redacted

    def analyze(
        self,
        container_info: Optional[Dict[str, Any]],
        container_logs: Optional[str] = None,
    ) -> List[DockerEvidence]:
        """
        Analyze container inspection data and produce structured diagnostic findings.
        """
        if not container_info:
            return []

        findings: List[DockerEvidence] = []

        container_id = container_info.get("Id") or container_info.get("id") or "unknown"
        container_name = container_info.get("Name") or container_info.get("name") or "unknown"
        state = container_info.get("State") or container_info.get("state") or {}

        # Handle flat or nested state dict
        status = state.get("Status") or state.get("status") or container_info.get("status") or "unknown"
        exit_code = state.get("ExitCode") if "ExitCode" in state else state.get("exit_code", container_info.get("exit_code"))
        restart_count = container_info.get("RestartCount") or container_info.get("restart_count") or 0
        oom_killed = state.get("OOMKilled") or state.get("oom_killed") or False
        error_msg = state.get("Error") or state.get("error") or ""

        # 1. Check Exit Code & Crashes
        if exit_code is not None and exit_code != 0:
            exit_meaning = EXIT_CODE_MAP.get(exit_code, f"Non-zero exit code ({exit_code})")
            severity = DockerSeverity.CRITICAL if exit_code in {137, 139} or oom_killed else DockerSeverity.HIGH

            findings.append(
                DockerEvidence(
                    source="Docker Container",
                    component=DockerComponent.CONTAINER,
                    category="container_non_zero_exit",
                    severity=severity,
                    message=f"Container '{container_name}' exited with error code {exit_code}: {exit_meaning}",
                    evidence=f"Container ID: {container_id[:12]}\nStatus: {status}\nExitCode: {exit_code}\nOOMKilled: {oom_killed}\nState Error: {error_msg or 'None'}",
                    confidence=0.98,
                    metadata={
                        "container_id": container_id,
                        "container_name": container_name,
                        "exit_code": exit_code,
                        "oom_killed": oom_killed,
                    },
                )
            )

        # 2. Crash Loop Check
        if restart_count > 1 and status in {"restarting", "exited", "dead"}:
            findings.append(
                DockerEvidence(
                    source="Docker Container",
                    component=DockerComponent.CONTAINER,
                    category="crash_loop_backoff",
                    severity=DockerSeverity.HIGH,
                    message=f"Container '{container_name}' is in a crash loop (Restart count: {restart_count}).",
                    evidence=f"Container has repeatedly failed and restarted {restart_count} times.",
                    confidence=0.95,
                    metadata={"restart_count": restart_count, "status": status},
                )
            )

        # 3. Healthcheck Status
        health = state.get("Health") or state.get("health") or {}
        health_status = health.get("Status") or health.get("status")
        if health_status == "unhealthy":
            failing_log_entries = health.get("Log") or health.get("log") or []
            last_log = failing_log_entries[-1].get("Output", "") if failing_log_entries else "Health check failed."
            findings.append(
                DockerEvidence(
                    source="Docker Container",
                    component=DockerComponent.CONTAINER,
                    category="container_unhealthy",
                    severity=DockerSeverity.HIGH,
                    message=f"Container '{container_name}' failed health check (Status: unhealthy).",
                    evidence=f"Health status: unhealthy\nLast check output: {last_log.strip()}",
                    confidence=0.92,
                    metadata={"health_status": health_status},
                )
            )

        # 4. Port Conflict Check (from network settings or state error)
        if "bind: address already in use" in error_msg.lower() or "port is already allocated" in error_msg.lower():
            findings.append(
                DockerEvidence(
                    source="Docker Container",
                    component=DockerComponent.CONTAINER,
                    category="port_binding_conflict",
                    severity=DockerSeverity.HIGH,
                    message=f"Port binding conflict prevented container '{container_name}' from starting.",
                    evidence=f"Docker error: {error_msg}",
                    confidence=0.98,
                )
            )

        # 5. Check Container Logs if provided
        if container_logs:
            from app.services.docker.log_analyzer import DockerLogAnalyzer
            log_analyzer = DockerLogAnalyzer()
            log_findings = log_analyzer.analyze(container_logs)
            for lf in log_findings:
                # Align source to Docker Container
                findings.append(
                    DockerEvidence(
                        source="Docker Container Logs",
                        component=lf.component,
                        category=lf.category,
                        severity=lf.severity,
                        message=lf.message,
                        evidence=lf.evidence,
                        confidence=lf.confidence,
                        metadata=lf.metadata,
                    )
                )

        # 6. If healthy and running with no issues
        if not findings and status == "running" and exit_code in {None, 0}:
            findings.append(
                DockerEvidence(
                    source="Docker Container",
                    component=DockerComponent.CONTAINER,
                    category="container_healthy",
                    severity=DockerSeverity.INFO,
                    message=f"Container '{container_name}' is currently running normally.",
                    evidence=f"Status: {status}, ExitCode: 0, RestartCount: {restart_count}",
                    confidence=1.0,
                    metadata={"status": status, "container_id": container_id},
                )
            )

        return findings
