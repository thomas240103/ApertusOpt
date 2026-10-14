"""Parse and validate raw LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from src.schemas import KnapsackProblem


class ParseError(ValueError):
    """Raised when an LLM response cannot be parsed into a valid problem."""


def parse_knapsack_response(
    raw_response: str, *, require_volume: bool = False
) -> KnapsackProblem:
    """Parse raw LLM text into a validated KnapsackProblem."""
    if not isinstance(raw_response, str):
        raise ParseError("Apertus response must be text.")
    try:
        json_text = extract_json(strip_code_fences(raw_response))
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON from Apertus: {exc.msg}") from exc

    if isinstance(data, dict) and set(data) == {"error"}:
        raise ParseError(f"Apertus could not formulate the problem: {data['error']}")

    try:
        problem = KnapsackProblem.model_validate(data)
    except ValidationError as exc:
        raise ParseError(f"Generated JSON failed schema validation: {exc}") from exc
    if require_volume and problem.volume_capacity is None:
        raise ParseError("Pallet mode requires volume_capacity and a volume for every pallet.")
    return problem


def strip_code_fences(text: str) -> str:
    """Remove accidental Markdown fences while preserving the JSON body."""
    stripped = text.strip()
    fence_pattern = r"^```(?:json)?\s*(.*?)\s*```$"
    match = re.match(fence_pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def extract_json(text: str) -> str:
    """Extract the first complete JSON object from text."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ParseError("No JSON object found in Apertus response.")

    return stripped[start : end + 1]


def parse_json(raw_response: str) -> dict[str, Any]:
    """Return validated knapsack data as a plain dictionary."""
    return parse_knapsack_response(raw_response).model_dump(exclude_none=True)
