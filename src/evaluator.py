"""Simple evaluation helpers for generated and solved problems."""

from __future__ import annotations

import json
import re
from typing import Any

from src.parser import ParseError, extract_json, parse_knapsack_response, strip_code_fences
from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


def evaluate_solution(problem: KnapsackProblem, solution: dict[str, Any]) -> dict[str, Any]:
    """Check feasibility and objective consistency for a knapsack solution."""
    items_by_name = {item.name: item for item in problem.items}
    selected_names = solution.get("selected_items", [])

    unknown_items = [name for name in selected_names if name not in items_by_name]
    total_weight = sum(items_by_name[name].weight for name in selected_names if name in items_by_name)
    total_value = sum(items_by_name[name].value for name in selected_names if name in items_by_name)

    return {
        "is_feasible": not unknown_items and total_weight <= problem.capacity,
        "unknown_items": unknown_items,
        "reported_total_weight_matches": total_weight == solution.get("total_weight"),
        "reported_total_value_matches": total_value == solution.get("total_value"),
        "computed_total_weight": int(total_weight) if float(total_weight).is_integer() else total_weight,
        "computed_total_value": int(total_value) if float(total_value).is_integer() else total_value,
    }


def evaluate_case(case: dict[str, Any], raw_response: str) -> dict[str, Any]:
    """Compare an Apertus response with a hand-checked benchmark reference."""
    result: dict[str, Any] = {"id": case["id"], "passed": False}
    if not isinstance(raw_response, str):
        return {**result, "error": "Apertus response must be text."}

    if "expected_error_terms" in case:
        try:
            data = json.loads(extract_json(strip_code_fences(raw_response)))
        except (ParseError, json.JSONDecodeError) as exc:
            return {**result, "error_reported": False, "error": str(exc)}
        message = data.get("error") if isinstance(data, dict) else None
        # Require an explicit error identifying both the missing field and item.
        reported = (
            isinstance(message, str)
            and bool(message.strip())
            and set(data) == {"error"}
            and all(
                any(
                    re.search(r"\b" + re.escape(term) + r"\b", message, re.IGNORECASE)
                    for term in alternatives)
                for alternatives in case["expected_error_terms"]
            )
        )
        return {**result, "passed": reported, "error_reported": reported,
                "message": message}

    try:
        problem = parse_knapsack_response(raw_response)
    except ParseError as exc:
        return {**result, "schema_valid": False, "error": str(exc)}

    expected = KnapsackProblem.model_validate(case["expected_problem"])
    actual_data = problem.model_dump()
    expected_data = expected.model_dump()
    for data in (actual_data, expected_data):
        data["items"] = sorted(data["items"], key=lambda item: item["name"])
    formulation_matches = actual_data == expected_data

    solution = solve_knapsack(problem)
    reference = case["expected_solution"]
    solution_matches = (
        solution["status"] == reference["status"]
        and sorted(solution["selected_items"]) == sorted(reference["selected_items"])
        and solution["total_weight"] == reference["total_weight"]
        and solution["total_value"] == reference["total_value"]
    )
    return {
        **result,
        "passed": formulation_matches and solution_matches,
        "schema_valid": True,
        "formulation_matches": formulation_matches,
        "solution_matches": solution_matches,
        "solution": solution,
    }
