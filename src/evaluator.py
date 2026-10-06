"""Simple evaluation helpers for generated and solved problems."""

from __future__ import annotations

from typing import Any

from src.schemas import KnapsackProblem


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
