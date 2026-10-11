"""
Dockerfile Static Analyzer.

Performs rule-based static analysis on raw Dockerfile content to detect
common authoring mistakes. Does NOT require a Docker daemon.

Findings are rated by severity and carry explicit confidence scores that
reflect what can genuinely be inferred from static inspection alone.
"""

import logging
import re
from typing import List, Optional

from app.services.docker.schemas import DockerComponent, DockerEvidence, DockerSeverity

logger = logging.getLogger(__name__)

# ── Known base image patterns ───────────────────────────────────────────────
# Images that suggest a valid well-known base
WELL_KNOWN_BASES = {
    "ubuntu", "debian", "alpine", "centos", "fedora", "amazonlinux",
    "python", "node", "ruby", "golang", "java", "openjdk", "adoptopenjdk",
    "eclipse-temurin", "php", "nginx", "apache", "httpd", "redis", "postgres",
    "postgresql", "mysql", "mariadb", "mongo", "mongodb", "elasticsearch",
    "kibana", "grafana", "prometheus", "scratch", "busybox", "distroless",
    "gcr.io", "mcr.microsoft.com", "public.ecr.aws",
}

# Tags that are known to be unstable / bad practice
MUTABLE_TAGS = {"latest", "master", "main", "dev", "develop", "trunk", "edge", "nightly"}

# Secret-bearing environment variable key patterns (same logic as LogProcessor)
SECRET_KEY_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|credential|auth[_-]?key|auth[_-]?token)",
    re.IGNORECASE,
)

# Dockerfile instruction regex
FROM_PATTERN = re.compile(r"^\s*FROM\s+(.+?)(?:\s+AS\s+\S+)?\s*$", re.IGNORECASE | re.MULTILINE)
COPY_PATTERN = re.compile(r"^\s*COPY\s+(.+)$", re.IGNORECASE | re.MULTILINE)
RUN_PATTERN = re.compile(r"^\s*RUN\s+(.+)$", re.IGNORECASE | re.MULTILINE)
WORKDIR_PATTERN = re.compile(r"^\s*WORKDIR\s+(.+)$", re.IGNORECASE | re.MULTILINE)
CMD_PATTERN = re.compile(r"^\s*CMD\s+(.+)$", re.IGNORECASE | re.MULTILINE)
ENTRYPOINT_PATTERN = re.compile(r"^\s*ENTRYPOINT\s+(.+)$", re.IGNORECASE | re.MULTILINE)
EXPOSE_PATTERN = re.compile(r"^\s*EXPOSE\s+(.+)$", re.IGNORECASE | re.MULTILINE)
ENV_PATTERN = re.compile(r"^\s*ENV\s+(.+)$", re.IGNORECASE | re.MULTILINE)
ARG_PATTERN = re.compile(r"^\s*ARG\s+(\S+)", re.IGNORECASE | re.MULTILINE)
ADD_PATTERN = re.compile(r"^\s*ADD\s+(.+)$", re.IGNORECASE | re.MULTILINE)


class DockerfileAnalyzer:
    """Static analyzer for Dockerfile content."""

    def analyze(self, dockerfile_content: Optional[str]) -> List[DockerEvidence]:
        """
        Analyze raw Dockerfile content and return structured evidence.

        Returns an empty list if content is None.
        Returns a single critical finding if content is empty.
        """
        if dockerfile_content is None:
            return [
                DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="missing_dockerfile",
                    severity=DockerSeverity.CRITICAL,
                    message="No Dockerfile content was provided for analysis.",
                    evidence="Dockerfile content is absent. The build cannot proceed without a valid Dockerfile.",
                    confidence=1.0,
                )
            ]

        if not dockerfile_content.strip():
            return [
                DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="empty_dockerfile",
                    severity=DockerSeverity.CRITICAL,
                    message="Dockerfile is empty.",
                    evidence="The provided Dockerfile contains no instructions.",
                    confidence=1.0,
                )
            ]

        findings: List[DockerEvidence] = []
        findings.extend(self._check_from_instructions(dockerfile_content))
        findings.extend(self._check_copy_instructions(dockerfile_content))
        findings.extend(self._check_run_instructions(dockerfile_content))
        findings.extend(self._check_workdir(dockerfile_content))
        findings.extend(self._check_cmd_entrypoint(dockerfile_content))
        findings.extend(self._check_env_secrets(dockerfile_content))
        findings.extend(self._check_add_vs_copy(dockerfile_content))
        findings.extend(self._check_expose(dockerfile_content))

        logger.debug(
            "Dockerfile analysis complete | findings=%d",
            len(findings),
        )
        return findings

    # ── FROM instruction checks ──────────────────────────────────────────────

    def _check_from_instructions(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        from_matches = FROM_PATTERN.findall(content)

        if not from_matches:
            findings.append(DockerEvidence(
                source="Dockerfile",
                component=DockerComponent.DOCKERFILE,
                category="missing_from",
                severity=DockerSeverity.CRITICAL,
                message="No FROM instruction found in Dockerfile.",
                evidence="Every valid Dockerfile must begin with a FROM instruction.",
                confidence=1.0,
            ))
            return findings

        for raw_image in from_matches:
            raw_image = raw_image.strip()

            # Skip ARG-based dynamic FROM (e.g. FROM $BASE_IMAGE)
            if raw_image.startswith("$") or raw_image.startswith("${"):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="dynamic_base_image",
                    severity=DockerSeverity.LOW,
                    message=f"FROM uses a dynamic ARG value: '{raw_image}'. "
                            "Verify the ARG is correctly declared and supplied at build time.",
                    evidence=f"FROM {raw_image}",
                    confidence=0.7,
                    metadata={"raw_reference": raw_image},
                ))
                continue

            # Detect scratch / distroless (valid, no further checks)
            if raw_image.lower() in ("scratch", "distroless"):
                continue

            # Check for missing tag (uses implicit :latest)
            if ":" not in raw_image and "@" not in raw_image:
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="no_image_tag",
                    severity=DockerSeverity.MEDIUM,
                    message=f"Base image '{raw_image}' has no explicit tag. "
                            "Implicit ':latest' can cause non-reproducible builds.",
                    evidence=f"FROM {raw_image}",
                    confidence=0.95,
                    metadata={"image": raw_image},
                ))
            else:
                # Check for known-mutable tags
                tag_match = re.search(r":([^@\s]+)", raw_image)
                if tag_match:
                    tag = tag_match.group(1).lower()
                    if tag in MUTABLE_TAGS:
                        findings.append(DockerEvidence(
                            source="Dockerfile",
                            component=DockerComponent.DOCKERFILE,
                            category="mutable_tag",
                            severity=DockerSeverity.LOW,
                            message=f"Base image '{raw_image}' uses a mutable tag ':{tag}'. "
                                    "Pin to a specific digest or version tag for reproducibility.",
                            evidence=f"FROM {raw_image}",
                            confidence=0.9,
                            metadata={"image": raw_image, "tag": tag},
                        ))

        return findings

    # ── COPY instruction checks ──────────────────────────────────────────────

    def _check_copy_instructions(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        copy_matches = COPY_PATTERN.findall(content)

        for copy_args in copy_matches:
            copy_args = copy_args.strip()

            # COPY --from=<stage> is a multi-stage build copy – skip
            if copy_args.lower().startswith("--from="):
                continue

            # Detect absolute source paths (almost always wrong)
            parts = copy_args.split()
            if len(parts) >= 2:
                src = parts[0]
                if src.startswith("/") and not src.startswith("//"):
                    findings.append(DockerEvidence(
                        source="Dockerfile",
                        component=DockerComponent.DOCKERFILE,
                        category="copy_absolute_src",
                        severity=DockerSeverity.MEDIUM,
                        message=f"COPY uses an absolute source path '{src}'. "
                                "Docker COPY sources must be relative to the build context.",
                        evidence=f"COPY {copy_args}",
                        confidence=0.85,
                        metadata={"src": src},
                    ))

        return findings

    # ── RUN instruction checks ───────────────────────────────────────────────

    def _check_run_instructions(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        run_matches = RUN_PATTERN.findall(content)

        for run_cmd in run_matches:
            run_cmd_stripped = run_cmd.strip()

            # Package managers without cache cleanup
            if re.search(r"\bapt-get\s+install\b", run_cmd_stripped, re.IGNORECASE):
                if "--no-install-recommends" not in run_cmd_stripped:
                    findings.append(DockerEvidence(
                        source="Dockerfile",
                        component=DockerComponent.DOCKERFILE,
                        category="apt_no_recommends",
                        severity=DockerSeverity.LOW,
                        message="apt-get install missing '--no-install-recommends'. "
                                "This may increase image size unnecessarily.",
                        evidence=f"RUN {run_cmd_stripped[:200]}",
                        confidence=0.8,
                    ))
                if "rm -rf /var/lib/apt/lists" not in run_cmd_stripped:
                    findings.append(DockerEvidence(
                        source="Dockerfile",
                        component=DockerComponent.DOCKERFILE,
                        category="apt_cache_not_cleaned",
                        severity=DockerSeverity.LOW,
                        message="apt-get install does not clean apt cache in the same RUN layer. "
                                "Add '&& rm -rf /var/lib/apt/lists/*' to reduce image size.",
                        evidence=f"RUN {run_cmd_stripped[:200]}",
                        confidence=0.8,
                    ))

            # curl | bash – security concern
            if re.search(r"curl\s+.+\|\s*(?:ba)?sh", run_cmd_stripped, re.IGNORECASE):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="curl_pipe_sh",
                    severity=DockerSeverity.MEDIUM,
                    message="RUN pipes curl output directly into sh/bash. "
                            "This is a security risk and may fail in restricted environments.",
                    evidence=f"RUN {run_cmd_stripped[:200]}",
                    confidence=0.9,
                ))

        return findings

    # ── WORKDIR checks ───────────────────────────────────────────────────────

    def _check_workdir(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        workdir_matches = WORKDIR_PATTERN.findall(content)

        if not workdir_matches:
            # Only flag if there are COPY/RUN instructions, implying an app is expected
            has_copy = bool(COPY_PATTERN.search(content))
            has_run = bool(RUN_PATTERN.search(content))
            if has_copy or has_run:
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="no_workdir",
                    severity=DockerSeverity.LOW,
                    message="No WORKDIR instruction found. Operations will execute in '/' by default. "
                            "Explicitly set WORKDIR for predictable behavior.",
                    evidence="Missing WORKDIR instruction with COPY/RUN present.",
                    confidence=0.75,
                ))

        for workdir in workdir_matches:
            workdir = workdir.strip()
            if not workdir.startswith("/") and not workdir.startswith("$"):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="relative_workdir",
                    severity=DockerSeverity.MEDIUM,
                    message=f"WORKDIR '{workdir}' is a relative path. "
                            "WORKDIR should be an absolute path to avoid ambiguity.",
                    evidence=f"WORKDIR {workdir}",
                    confidence=0.9,
                    metadata={"workdir": workdir},
                ))

        return findings

    # ── CMD / ENTRYPOINT checks ───────────────────────────────────────────────

    def _check_cmd_entrypoint(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        cmd_matches = CMD_PATTERN.findall(content)
        ep_matches = ENTRYPOINT_PATTERN.findall(content)

        has_cmd = bool(cmd_matches)
        has_ep = bool(ep_matches)

        if not has_cmd and not has_ep:
            findings.append(DockerEvidence(
                source="Dockerfile",
                component=DockerComponent.DOCKERFILE,
                category="no_cmd_or_entrypoint",
                severity=DockerSeverity.HIGH,
                message="No CMD or ENTRYPOINT instruction found. "
                        "The container will not know what process to run on startup.",
                evidence="Missing CMD and ENTRYPOINT instructions.",
                confidence=0.95,
            ))

        # Shell-form CMD/ENTRYPOINT (can cause signal handling issues)
        for cmd_val in cmd_matches:
            cmd_val = cmd_val.strip()
            if not cmd_val.startswith("["):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="cmd_shell_form",
                    severity=DockerSeverity.LOW,
                    message="CMD uses shell form instead of exec form (JSON array). "
                            "Shell form wraps the command in /bin/sh -c, which may prevent "
                            "signal forwarding and proper container shutdown.",
                    evidence=f"CMD {cmd_val[:200]}",
                    confidence=0.85,
                ))

        for ep_val in ep_matches:
            ep_val = ep_val.strip()
            if not ep_val.startswith("["):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="entrypoint_shell_form",
                    severity=DockerSeverity.LOW,
                    message="ENTRYPOINT uses shell form instead of exec form (JSON array). "
                            "Shell form may prevent graceful signal handling.",
                    evidence=f"ENTRYPOINT {ep_val[:200]}",
                    confidence=0.85,
                ))

        return findings

    # ── ENV secret exposure checks ────────────────────────────────────────────

    def _check_env_secrets(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        env_matches = ENV_PATTERN.findall(content)

        for env_line in env_matches:
            env_line = env_line.strip()
            # ENV can be: KEY=VALUE, KEY VALUE, or multiple KEY=VALUE pairs
            # Extract key names
            keys = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)(?:=|\s)", env_line)
            for key in keys:
                if SECRET_KEY_PATTERN.search(key):
                    findings.append(DockerEvidence(
                        source="Dockerfile",
                        component=DockerComponent.DOCKERFILE,
                        category="env_secret_baked_in",
                        severity=DockerSeverity.HIGH,
                        message=f"ENV instruction sets a key '{key}' that appears to be a secret. "
                                "Secrets must NOT be baked into Dockerfile ENV instructions. "
                                "Use Docker secrets, runtime env vars, or build secrets instead.",
                        evidence=f"ENV {key}=<REDACTED>",
                        confidence=0.8,
                        metadata={"key": key},
                    ))

        return findings

    # ── ADD vs COPY checks ────────────────────────────────────────────────────

    def _check_add_vs_copy(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        add_matches = ADD_PATTERN.findall(content)

        for add_args in add_matches:
            add_args = add_args.strip()
            # ADD is valid for remote URLs and tar extraction; flag otherwise
            if not (add_args.startswith("http://") or add_args.startswith("https://")
                    or add_args.endswith(".tar.gz") or add_args.endswith(".tgz")
                    or add_args.endswith(".tar.bz2") or add_args.endswith(".tar.xz")):
                findings.append(DockerEvidence(
                    source="Dockerfile",
                    component=DockerComponent.DOCKERFILE,
                    category="add_instead_of_copy",
                    severity=DockerSeverity.LOW,
                    message="ADD is used where COPY would be more appropriate. "
                            "Prefer COPY for plain file copies as ADD has implicit behaviors "
                            "(URL fetch, tar extraction) that may be unintended.",
                    evidence=f"ADD {add_args[:200]}",
                    confidence=0.75,
                ))

        return findings

    # ── EXPOSE checks ────────────────────────────────────────────────────────

    def _check_expose(self, content: str) -> List[DockerEvidence]:
        findings: List[DockerEvidence] = []
        expose_matches = EXPOSE_PATTERN.findall(content)

        for expose_val in expose_matches:
            expose_val = expose_val.strip()
            # Check for common well-known port collisions in documentation
            ports = expose_val.split()
            for port_entry in ports:
                port_num = port_entry.split("/")[0]
                try:
                    port_int = int(port_num)
                    if port_int < 1 or port_int > 65535:
                        findings.append(DockerEvidence(
                            source="Dockerfile",
                            component=DockerComponent.DOCKERFILE,
                            category="invalid_expose_port",
                            severity=DockerSeverity.MEDIUM,
                            message=f"EXPOSE declares port {port_int} which is outside the valid range 1–65535.",
                            evidence=f"EXPOSE {expose_val}",
                            confidence=0.95,
                            metadata={"port": port_int},
                        ))
                except ValueError:
                    # Could be $PORT or similar — skip
                    pass

        return findings
