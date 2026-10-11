"""
Docker Image Reference Analyzer.

Validates Docker image references, parses registry/repository/tag/digest components,
and produces structured findings based on syntactical checks and known image reference patterns.
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

# Regex for parsing Docker image references according to Docker/OCI spec:
# [REGISTRY[:PORT]/][NAMESPACE/]REPOSITORY[:TAG][@DIGEST]
IMAGE_REF_PATTERN = re.compile(
    r"^(?:(?P<registry>(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+(?::\d+)?|[a-zA-Z0-9-]+:\d+)/)?"
    r"(?:(?P<namespace>[a-zA-Z0-9_.-]+)/)?"
    r"(?P<repository>[a-zA-Z0-9_.-]+)"
    r"(?::(?P<tag>[a-zA-Z0-9_.-]+))?"
    r"(?:@(?P<digest>sha256:[a-fA-F0-9]{64}))?$"
)

# Common mutable / suspicious tags
SUSPICIOUS_TAGS = {"latest", "master", "main", "dev", "edge", "nightly", "canary", "test"}

# Known public registries
KNOWN_REGISTRIES = {
    "docker.io", "registry-1.docker.io", "ghcr.io", "quay.io", "gcr.io",
    "mcr.microsoft.com", "public.ecr.aws"
}


class DockerImageAnalyzer:
    """Analyzer for Docker image references and tag hygiene."""

    def parse_reference(self, image_ref: str) -> Optional[Dict[str, Optional[str]]]:
        """
        Parse an image reference into registry, namespace, repository, tag, and digest.
        Returns None if the reference syntax is completely invalid.
        """
        if not image_ref or not image_ref.strip():
            return None

        clean_ref = image_ref.strip()
        match = IMAGE_REF_PATTERN.match(clean_ref)
        if not match:
            return None

        groups = match.groupdict()
        return {
            "raw": clean_ref,
            "registry": groups.get("registry") or "docker.io",
            "namespace": groups.get("namespace"),
            "repository": groups.get("repository"),
            "tag": groups.get("tag"),
            "digest": groups.get("digest"),
        }

    def analyze(self, image_ref: Optional[str]) -> List[DockerEvidence]:
        """
        Validate an image reference and return structured Docker evidence.
        """
        if not image_ref or not image_ref.strip():
            return [
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="missing_image_reference",
                    severity=DockerSeverity.HIGH,
                    message="No image reference provided for validation.",
                    evidence="Image reference is empty or null.",
                    confidence=1.0,
                )
            ]

        ref = image_ref.strip()
        parsed = self.parse_reference(ref)

        if not parsed or not parsed.get("repository"):
            return [
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="invalid_image_reference",
                    severity=DockerSeverity.HIGH,
                    message=f"Invalid Docker image reference format: '{ref}'",
                    evidence=f"The string '{ref}' does not follow OCI / Docker repository naming conventions.",
                    confidence=0.95,
                    metadata={"raw_reference": ref},
                )
            ]

        findings: List[DockerEvidence] = []
        tag = parsed.get("tag")
        digest = parsed.get("digest")
        repo = parsed.get("repository")
        registry = parsed.get("registry")

        # 1. Missing tag check
        if not tag and not digest:
            findings.append(
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="missing_tag",
                    severity=DockerSeverity.MEDIUM,
                    message=f"Image reference '{ref}' does not specify a tag and will implicitly default to ':latest'.",
                    evidence=f"Reference '{ref}' lacks an explicit tag or sha256 digest pin.",
                    confidence=0.90,
                    metadata=parsed,
                )
            )
        elif tag and tag.lower() in SUSPICIOUS_TAGS:
            findings.append(
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="mutable_tag_used",
                    severity=DockerSeverity.LOW,
                    message=f"Image reference '{ref}' uses mutable tag ':{tag}'.",
                    evidence=f"Mutable tag ':{tag}' can cause non-reproducible builds or unexpected upstream breakage.",
                    confidence=0.85,
                    metadata=parsed,
                )
            )

        # 2. Check uppercase or illegal characters in repository/namespace
        if any(c.isupper() for c in (parsed.get("namespace") or "")) or any(c.isupper() for c in (repo or "")):
            findings.append(
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="uppercase_repository_name",
                    severity=DockerSeverity.HIGH,
                    message=f"Repository name contains uppercase characters in '{ref}'. Docker repositories must be lowercase.",
                    evidence=f"Docker OCI specification strictly requires lowercase characters for repository names: '{ref}'.",
                    confidence=0.98,
                    metadata=parsed,
                )
            )

        # 3. Informational reference confirmation
        if not findings:
            findings.append(
                DockerEvidence(
                    source="Docker Image",
                    component=DockerComponent.IMAGE,
                    category="valid_image_reference",
                    severity=DockerSeverity.INFO,
                    message=f"Image reference '{ref}' is syntactically valid (registry: {registry}, repo: {repo}, tag: {tag or 'pinned by digest'}).",
                    evidence=f"Valid OCI image reference: {ref}",
                    confidence=1.0,
                    metadata=parsed,
                )
            )

        return findings
