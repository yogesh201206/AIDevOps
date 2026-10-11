"""
Safe Read-Only Docker Command Executor.

Executes strictly allowlisted, read-only Docker CLI inspection commands with:
- Strict sub-command allowlist (version, info, ps, inspect, images, logs)
- Parameter sanitization (forbidding shell metacharacters, rm, prune, exec, etc.)
- Fixed execution timeouts
- Subprocess error handling and stderr capture
- Maximum output size limits
- Secret redaction on stdout/stderr output

SAFETY RULE: Never execute mutating commands (rm, rmi, prune, exec, run, build, kill, stop, etc.)
"""

import asyncio
import logging
import re
import shlex
from typing import List, Optional

from app.services.docker.exceptions import (
    DockerCommandError,
    DockerCommandForbiddenError,
    DockerNotAvailableError,
    DockerTimeoutError,
)

logger = logging.getLogger(__name__)

# Strict allowlist of permissible read-only Docker CLI subcommands
ALLOWED_SUBCOMMANDS = {
    "version",
    "info",
    "ps",
    "inspect",
    "images",
    "logs",
}

# Dangerous / mutating keywords explicitly blocked even if passed as arguments
DISALLOWED_PATTERNS = re.compile(
    r"(?:rm|rmi|prune|system\s+prune|exec|run|kill|stop|start|restart|build|push|tag|"
    r"commit|attach|cp|pause|unpause|rename|update|save|load|export|import|login|logout)",
    re.IGNORECASE,
)

# Secret pattern for redaction
SECRET_REDACT_PATTERN = re.compile(
    r"((?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|credential|auth)\s*[=:]\s*)([^\s\"'&,;]+)",
    re.IGNORECASE,
)

# Dangerous shell characters forbidden in arguments
SHELL_METACHRACTERS = re.compile(r"[;&|`$<>{}\[\]\n\r]")


class SafeDockerExecutor:
    """Safe, sandboxed executor for read-only Docker CLI inspection."""

    def __init__(
        self,
        default_timeout_seconds: float = 8.0,
        max_output_chars: int = 50_000,
    ):
        self.default_timeout_seconds = default_timeout_seconds
        self.max_output_chars = max_output_chars

    def sanitize_args(self, subcommand: str, args: Optional[List[str]] = None) -> List[str]:
        """
        Validate and assemble command arguments against the read-only allowlist.
        Raises DockerCommandForbiddenError on violations.
        """
        clean_sub = subcommand.strip().lower()

        if clean_sub not in ALLOWED_SUBCOMMANDS:
            raise DockerCommandForbiddenError(
                f"Subcommand 'docker {clean_sub}' is not permitted. Allowed commands: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}"
            )

        cmd_tokens = ["docker", clean_sub]

        if args:
            for arg in args:
                arg_clean = arg.strip()
                # Check for forbidden shell metacharacters
                if SHELL_METACHRACTERS.search(arg_clean):
                    raise DockerCommandForbiddenError(
                        f"Argument contains illegal shell metacharacters: '{arg_clean}'"
                    )

                # Check for mutating subcommands passed as flags/options
                tokens = arg_clean.split()
                for t in tokens:
                    if DISALLOWED_PATTERNS.fullmatch(t.lower()):
                        raise DockerCommandForbiddenError(
                            f"Argument '{arg_clean}' contains prohibited mutating action: '{t}'"
                        )

                cmd_tokens.append(arg_clean)

        return cmd_tokens

    def redact_secrets(self, text: str) -> str:
        """Sanitize secrets from command output."""
        if not text:
            return ""
        return SECRET_REDACT_PATTERN.sub(r"\g<1>[REDACTED]", text)

    async def execute(
        self,
        subcommand: str,
        args: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Execute an allowlisted Docker command safely via asyncio subprocess.
        """
        cmd_tokens = self.sanitize_args(subcommand, args)
        timeout_val = timeout or self.default_timeout_seconds

        logger.debug("Executing safe Docker command: %s (timeout=%.1fs)", " ".join(cmd_tokens), timeout_val)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_tokens,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_val,
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                raise DockerTimeoutError(
                    f"Docker command 'docker {subcommand}' timed out after {timeout_val:.1f}s."
                )

            stdout = stdout_data.decode("utf-8", errors="replace")
            stderr = stderr_data.decode("utf-8", errors="replace")

            if process.returncode != 0:
                combined_err = (stderr or stdout).strip()
                if "Cannot connect to the Docker daemon" in combined_err or "Is the docker daemon running" in combined_err:
                    raise DockerNotAvailableError(
                        f"Docker daemon is not reachable: {combined_err}"
                    )
                raise DockerCommandError(
                    f"Docker command failed (exit code {process.returncode}): {combined_err}"
                )

            output = stdout.strip()

            # Truncate output if larger than limit
            if len(output) > self.max_output_chars:
                output = output[: self.max_output_chars] + "\n[... output truncated to safety limit ...]"

            return self.redact_secrets(output)

        except FileNotFoundError:
            raise DockerNotAvailableError("Docker CLI binary ('docker') was not found in system PATH.")
        except (DockerException, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise DockerCommandError(f"Unexpected error executing Docker command: {str(exc)}")
