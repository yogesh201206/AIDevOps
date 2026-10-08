"""
Parser and validator for structured AI output.

Extracts, normalizes, and validates JSON diagnostic reports from LLM responses,
resilient against markdown envelopes, commentary, and slight formatting variations.
"""

import json
import logging
import re
from typing import List

from pydantic import BaseModel, Field, ValidationError

from app.services.ai.exceptions import AIParseError
from app.services.investigation.schemas import Evidence, RootCause, SuggestedFix

logger = logging.getLogger(__name__)


class AIOutputSchema(BaseModel):
    """Pydantic model representing expected structured AI diagnostic output."""

    summary: str = Field(..., min_length=5, description="Executive summary of diagnosis")
    root_causes: List[RootCause] = Field(..., min_length=1, description="At least one root cause")
    evidence: List[Evidence] = Field(default_factory=list, description="Supporting log evidence")
    affected_components: List[str] = Field(default_factory=list, description="Affected components")
    severity: str = Field(default="high", description="Severity (critical, high, medium, low)")
    suggested_fixes: List[SuggestedFix] = Field(default_factory=list, description="Suggested fixes")
    validation_steps: List[str] = Field(default_factory=list, description="Validation steps")
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score between 0.0 and 1.0",
    )


def extract_json_content(raw_text: str) -> str:
    """
    Extract raw JSON string from potentially markdown-fenced or commented LLM text.
    """
    if not raw_text or not raw_text.strip():
        raise AIParseError("AI response was empty.")

    cleaned = raw_text.strip()

    # Case 1: Markdown code block (```json ... ``` or ``` ...)
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Case 2: Braced JSON somewhere in the text
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1].strip()

    return cleaned


def parse_ai_response(raw_text: str) -> AIOutputSchema:
    """
    Parse and validate raw AI response into AIOutputSchema.

    Raises AIParseError if JSON is invalid or fails Pydantic schema validation.
    """
    json_str = extract_json_content(raw_text)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to decode JSON from AI output: %s", exc)
        raise AIParseError(f"AI response did not contain valid JSON: {str(exc)}") from exc

    if not isinstance(data, dict):
        raise AIParseError("AI response root must be a JSON object.")

    # Validate overall_confidence range explicitly if present
    if "overall_confidence" in data:
        try:
            val = float(data["overall_confidence"])
            if val < 0.0 or val > 1.0:
                raise AIParseError(
                    f"Invalid overall_confidence score {val}. Must be between 0.0 and 1.0."
                )
        except (ValueError, TypeError) as exc:
            raise AIParseError(f"overall_confidence must be a number: {exc}") from exc

    # Validate root_causes confidence
    for idx, rc in enumerate(data.get("root_causes", [])):
        if isinstance(rc, dict) and "confidence" in rc:
            try:
                c_val = float(rc["confidence"])
                if c_val < 0.0 or c_val > 1.0:
                    raise AIParseError(
                        f"Root cause at index {idx} has invalid confidence {c_val}. Must be between 0.0 and 1.0."
                    )
            except (ValueError, TypeError) as exc:
                raise AIParseError(f"Root cause confidence must be a number: {exc}") from exc

    # Normalize severity string
    if "severity" in data and isinstance(data["severity"], str):
        data["severity"] = data["severity"].lower().strip()
        if data["severity"] not in {"critical", "high", "medium", "low"}:
            data["severity"] = "high"

    try:
        return AIOutputSchema.model_validate(data)
    except ValidationError as exc:
        logger.warning("Schema validation error on AI response: %s", exc)
        first_error = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        raise AIParseError(f"AI response schema validation failed: {first_error}") from exc
