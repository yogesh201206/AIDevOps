"""
Investigation Context Builder.

Synthesizes workflow run metadata, failed jobs, failed steps, preceding steps,
and sanitized diagnostic logs into a structured context for LLM incident analysis.
"""

from typing import List, Optional

from app.config import settings
from app.github.schemas import WorkflowJob, WorkflowRun, WorkflowStep
from app.services.investigation.log_processor import LogProcessor


class ContextBuilder:
    """Constructs structured diagnostic context for AI consumption."""

    def __init__(self, max_context_chars: Optional[int] = None):
        self.max_context_chars = (
            max_context_chars
            if max_context_chars is not None
            else settings.MAX_CONTEXT_CHARS
        )

    def build_context(
        self,
        owner: str,
        repo: str,
        run: WorkflowRun,
        jobs: List[WorkflowJob],
        logs_content: Optional[str] = None,
    ) -> str:
        """
        Assemble human-readable structured context block.
        """
        failed_jobs = [j for j in jobs if j.is_failed]
        successful_jobs = [j for j in jobs if not j.is_failed]

        parts: List[str] = []

        parts.append(f"Repository:\n{owner}/{repo}\n")
        parts.append(f"Workflow:\n{run.workflow_name}\n")
        parts.append(f"Run ID:\n{run.id}\n")
        parts.append(f"Branch:\n{run.branch}\n")
        commit_desc = f"{run.commit_short_sha}"
        if run.commit_message:
            commit_desc += f" (\"{run.commit_message}\")"
        parts.append(f"Commit:\n{commit_desc}\n")
        parts.append(f"Status:\n{run.status}\n")
        parts.append(f"Conclusion:\n{run.conclusion or 'unknown'}\n")

        # Job Summary
        parts.append(
            f"Jobs Summary:\nTotal jobs: {len(jobs)} | Failed jobs: {len(failed_jobs)} | Successful jobs: {len(successful_jobs)}\n"
        )

        # Detailed breakdown of failed jobs and their steps
        if failed_jobs:
            parts.append("--- FAILED JOBS & STEPS BREAKDOWN ---")
            for job in failed_jobs:
                parts.append(f"\nFailed Job: {job.name} (ID: {job.id}, Status: {job.status}, Conclusion: {job.conclusion})")

                # Find failed steps
                failed_steps = [s for s in job.steps if s.is_failed]
                for f_step in failed_steps:
                    parts.append(f"  -> Failed Step #{f_step.number}: {f_step.name}")
                    parts.append(f"     Status: {f_step.status} | Conclusion: {f_step.conclusion}")
                    if f_step.started_at and f_step.completed_at:
                        parts.append(f"     Duration: {f_step.started_at} to {f_step.completed_at}")

                    # Find immediately preceding step
                    step_idx = next(
                        (i for i, s in enumerate(job.steps) if s.number == f_step.number),
                        -1,
                    )
                    if step_idx > 0:
                        prev_step = job.steps[step_idx - 1]
                        parts.append(
                            f"     Immediately Preceding Step #{prev_step.number}: {prev_step.name} "
                            f"(Conclusion: {prev_step.conclusion})"
                        )
        else:
            parts.append("Failed Jobs: None detected in job list.")

        # Attach sanitized and truncated log excerpt
        if logs_content and logs_content.strip():
            normalized_logs = LogProcessor.normalize_log(logs_content)
            # Truncate if logs are long
            truncated_logs = LogProcessor.intelligent_truncate(
                normalized_logs,
                max_chars=settings.MAX_LOG_CHARS,
            )
            parts.append("\n--- RELEVANT EXECUTION LOGS ---")
            parts.append(truncated_logs)
        else:
            parts.append("\n--- RELEVANT EXECUTION LOGS ---")
            parts.append("No console log output was available for this workflow run.")

        raw_context = "\n".join(parts)

        # Enforce MAX_CONTEXT_CHARS limit
        if len(raw_context) > self.max_context_chars:
            allowed_log_budget = max(2000, self.max_context_chars - 3000)
            if logs_content:
                # Re-truncate logs with smaller budget
                t_logs = LogProcessor.intelligent_truncate(
                    LogProcessor.normalize_log(logs_content),
                    max_chars=allowed_log_budget,
                )
                # Reconstruct
                parts[-1] = t_logs
                raw_context = "\n".join(parts)
            if len(raw_context) > self.max_context_chars:
                raw_context = raw_context[: self.max_context_chars] + "\n[... context truncated to limit ...]"

        return raw_context
