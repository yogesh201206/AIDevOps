"""
Log Processor for GitHub Actions workflow logs.

Handles:
1. Secret and token redaction (defense in depth before AI transmission)
2. ANSI escape code stripping and normalization
3. Categorization of error lines, stack traces, exit codes, and dependency/network faults
4. Intelligent windowed truncation around error hot spots
"""

import re
from typing import Dict, List, Set, Tuple

# ── Redaction Regex Patterns ────────────────────────────────────────────────
SECRET_PATTERNS = [
    # GitHub Personal Access Tokens and Fine-Grained Tokens
    (re.compile(r"github_pat_[a-zA-Z0-9_]{50,}", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"gh[pousr]_[a-zA-Z0-9]{36,}", re.IGNORECASE), "[REDACTED_SECRET]"),
    # Private Keys (RSA, EC, OPENSSH, DSA)
    (
        re.compile(
            r"-----BEGIN (?:[A-Z0-9 ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+)?PRIVATE KEY-----",
            re.MULTILINE,
        ),
        "[REDACTED_SECRET]",
    ),
    # Bearer tokens
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.~]{20,}", re.IGNORECASE), "Bearer [REDACTED_SECRET]"),
    # Basic auth / connection strings with credentials
    (
        re.compile(
            r"(https?|ftp|postgres|postgresql|mysql|mongodb|redis)://([^:\s]+):([^@\s]+)@",
            re.IGNORECASE,
        ),
        r"\1://\2:[REDACTED_SECRET]@",
    ),
    # AWS Access Key IDs and Secrets
    (re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"), "[REDACTED_SECRET]"),
    (
        re.compile(
            r"(?:aws_secret_access_key|aws_session_token)\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{30,})['\"]?",
            re.IGNORECASE,
        ),
        r"aws_secret_access_key=[REDACTED_SECRET]",
    ),
    # Key / Secret / Token assignments (API_KEY=..., SECRET=..., etc.)
    (
        re.compile(
            r"(?:api[_-]?key|access[_-]?token|secret[_-]?token|client[_-]?secret|auth[_-]?token|auth[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?",
            re.IGNORECASE,
        ),
        r"token=[REDACTED_SECRET]",
    ),
    # Password assignments
    (
        re.compile(
            r"(?:password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{4,})['\"]?",
            re.IGNORECASE,
        ),
        r"password=[REDACTED_SECRET]",
    ),
]

# ANSI escape sequence stripper
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# GitHub log timestamp prefix stripper (e.g. "2026-10-08T17:15:32.1234567Z ")
GH_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s+",
    re.MULTILINE,
)

# Diagnostic indicators
ERROR_INDICATORS = [
    re.compile(r"\b(?:error|fatal|fail|failed|failure)\b", re.IGNORECASE),
    re.compile(r"\b(?:exception|traceback|panic)\b", re.IGNORECASE),
    re.compile(r"exit code\s+[1-9]\d*", re.IGNORECASE),
    re.compile(r"Process completed with exit code [1-9]\d*", re.IGNORECASE),
    re.compile(r"npm ERR!", re.IGNORECASE),
    re.compile(r"command not found", re.IGNORECASE),
    re.compile(r"\b(?:ModuleNotFoundError|ImportError|SyntaxError|NameError)\b", re.IGNORECASE),
    re.compile(r"\b(?:Permission denied|EACCES|Unauthorized|Forbidden)\b", re.IGNORECASE),
    re.compile(r"\b(?:Connection refused|ETIMEDOUT|getaddrinfo ENOTFOUND)\b", re.IGNORECASE),
]

WARNING_INDICATORS = [
    re.compile(r"\b(?:warn|warning|deprecated)\b", re.IGNORECASE),
]


class LogProcessor:
    """Processes, sanitizes, analyzes, and windows GitHub workflow execution logs."""

    @staticmethod
    def redact_secrets(text: str) -> str:
        """
        Scan and redact potential credentials, API keys, tokens, and private keys.
        Ensures raw secrets are never sent to AI providers or logged.
        """
        if not text:
            return ""

        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    @staticmethod
    def strip_ansi(text: str) -> str:
        """Remove ANSI color escape codes from console output."""
        if not text:
            return ""
        return ANSI_ESCAPE_PATTERN.sub("", text)

    @staticmethod
    def normalize_log(raw_text: str) -> str:
        """
        Normalize raw log output:
        - Strip ANSI sequences
        - Redact credentials
        - Normalize newline formats
        """
        if not raw_text:
            return ""

        clean = LogProcessor.strip_ansi(raw_text)
        clean = LogProcessor.redact_secrets(clean)
        clean = clean.replace("\r\n", "\n").replace("\r", "\n")
        return clean

    @staticmethod
    def analyze_log_content(log_text: str) -> Dict[str, List[str]]:
        """
        Categorize lines into error, warning, and fatal signals.
        """
        lines = log_text.splitlines()
        errors: List[str] = []
        warnings: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check errors first
            is_error = any(pattern.search(line_str) for pattern in ERROR_INDICATORS)
            if is_error:
                errors.append(line_str)
            else:
                is_warning = any(pattern.search(line_str) for pattern in WARNING_INDICATORS)
                if is_warning:
                    warnings.append(line_str)

        return {
            "error_lines": errors,
            "warning_lines": warnings,
        }

    @staticmethod
    def intelligent_truncate(
        log_text: str,
        max_chars: int = 50000,
        context_window: int = 6,
    ) -> str:
        """
        Truncate large logs intelligently.
        Rather than simply dropping the head or tail, preserves:
          1. Head (first 30 lines) - setup, commands invoked, environment
          2. Error regions (error lines + preceding/succeeding context_window lines)
          3. Tail (last 40 lines) - final failure summary, exit code
        If the total log is within max_chars, returns it unmodified.
        """
        if len(log_text) <= max_chars:
            return log_text

        lines = log_text.splitlines()
        total_lines = len(lines)
        if total_lines <= 80:
            # If line count is small but characters exceed limit, hard truncate tail
            return log_text[:max_chars] + f"\n[... truncated {len(log_text) - max_chars} characters ...]"

        # Collect error indices first (highest priority)
        error_indices: Set[int] = set()
        for i, line in enumerate(lines):
            if any(p.search(line) for p in ERROR_INDICATORS):
                start = max(0, i - context_window)
                end = min(total_lines, i + context_window + 1)
                for j in range(start, end):
                    error_indices.add(j)

        head_count = 10 if max_chars < 5000 else 30
        tail_count = 10 if max_chars < 5000 else 40

        keep_indices: Set[int] = set(error_indices)
        for i in range(min(head_count, total_lines)):
            keep_indices.add(i)
        for i in range(max(0, total_lines - tail_count), total_lines):
            keep_indices.add(i)

        sorted_indices = sorted(keep_indices)

        # Assemble truncated output with omitted gap markers
        result_lines: List[str] = []
        last_idx = -1

        for idx in sorted_indices:
            if last_idx != -1 and idx > last_idx + 1:
                omitted_count = idx - last_idx - 1
                result_lines.append(f"\n[... {omitted_count} lines omitted ...]\n")
            result_lines.append(lines[idx])
            last_idx = idx

        assembled = "\n".join(result_lines)

        # If still over max_chars, preserve both the error region and tail
        if len(assembled) > max_chars:
            half = max(200, (max_chars - 60) // 2)
            omitted = len(assembled) - (half * 2)
            assembled = (
                assembled[:half]
                + f"\n[... {omitted} characters omitted ...]\n"
                + assembled[-half:]
            )

        return assembled
