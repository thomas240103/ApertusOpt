"""Simple evaluation helpers for generated and solved problems."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from src.parser import ParseError, extract_json, parse_knapsack_response, strip_code_fences
from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


def evaluate_solution(problem: KnapsackProblem, solution: dict[str, Any]) -> dict[str, Any]:
    """Check feasibility and objective consistency for a knapsack solution."""
    items_by_name = {item.name: item for item in problem.items}
    selected_names = solution.get("selected_items", [])

    unknown_items = [name for name in selected_names if name not in items_by_name]
    duplicate_items = sorted({name for name in selected_names if selected_names.count(name) > 1})
    chosen = [items_by_name[name] for name in selected_names if name in items_by_name]
    total_weight = sum((Decimal(str(item.weight)) for item in chosen), Decimal(0))
    total_value = sum((Decimal(str(item.value)) for item in chosen), Decimal(0))
    weight_ok = total_weight <= Decimal(str(problem.capacity))

    result = {
        "is_feasible": (solution.get("status") in ("OPTIMAL", "FEASIBLE")
                        and not unknown_items and not duplicate_items and weight_ok),
        "unknown_items": unknown_items,
        "duplicate_items": duplicate_items,
        "weight_within_capacity": weight_ok,
        "reported_total_weight_matches": float(total_weight) == solution.get("total_weight"),
        "reported_total_value_matches": float(total_value) == solution.get("total_value"),
        "computed_total_weight": float(total_weight),
        "computed_total_value": float(total_value),
    }
    if problem.volume_capacity is not None:
        total_volume = sum((Decimal(str(item.volume)) for item in chosen), Decimal(0))
        volume_ok = total_volume <= Decimal(str(problem.volume_capacity))
        result.update({
            "is_feasible": result["is_feasible"] and volume_ok,
            "volume_within_capacity": volume_ok,
            "reported_total_volume_matches": float(total_volume) == solution.get("total_volume"),
            "computed_total_volume": float(total_volume),
        })
    return result


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
        problem = parse_knapsack_response(
            raw_response, require_volume="volume_capacity" in case["expected_problem"]
        )
    except ParseError as exc:
        return {**result, "schema_valid": False, "error": str(exc)}

    expected = KnapsackProblem.model_validate(case["expected_problem"])
    actual_data = problem.model_dump()
    expected_data = expected.model_dump()
    for data in (actual_data, expected_data):
        data["items"] = sorted(data["items"], key=lambda item: item["name"])
    formulation_matches = actual_data == expected_data

    try:
        solution = solve_knapsack(problem)
    except ValueError as exc:
        return {**result, "schema_valid": True, "error": str(exc)}
    reference = case["expected_solution"]
    solution_matches = (
        solution["status"] == reference["status"]
        and sorted(solution["selected_items"]) == sorted(reference["selected_items"])
        and solution["total_weight"] == reference["total_weight"]
        and solution["total_value"] == reference["total_value"]
        and solution.get("total_volume") == reference.get("total_volume")
    )
    return {
        **result,
        "passed": formulation_matches and solution_matches,
        "schema_valid": True,
        "formulation_matches": formulation_matches,
        "solution_matches": solution_matches,
        "solution": solution,
    }
