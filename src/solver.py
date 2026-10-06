"""OR-Tools solver for the 0/1 knapsack MVP."""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from src.schemas import KnapsackProblem


def solve_knapsack(problem: KnapsackProblem) -> dict[str, Any]:
    """Solve a validated 0/1 knapsack problem with OR-Tools CP-SAT."""
    model = cp_model.CpModel()
    selected = [
        model.new_bool_var(f"select_{_safe_var_name(item.name)}")
        for item in problem.items
    ]

    scale = _numeric_scale(
        [problem.capacity]
        + [item.weight for item in problem.items]
        + [item.value for item in problem.items]
    )
    weights = [_to_int(item.weight, scale) for item in problem.items]
    values = [_to_int(item.value, scale) for item in problem.items]
    capacity = _to_int(problem.capacity, scale)

    model.add(sum(weights[i] * selected[i] for i in range(len(selected))) <= capacity)
    model.maximize(sum(values[i] * selected[i] for i in range(len(selected))))

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": solver.status_name(status),
            "selected_items": [],
            "total_weight": 0,
            "total_value": 0,
        }

    selected_items = [
        item.name for item, variable in zip(problem.items, selected) if solver.value(variable)
    ]
    total_weight = sum(
        item.weight
        for item, variable in zip(problem.items, selected)
        if solver.value(variable)
    )
    total_value = sum(
        item.value for item, variable in zip(problem.items, selected) if solver.value(variable)
    )

    return {
        "status": solver.status_name(status),
        "selected_items": selected_items,
        "total_weight": _clean_number(total_weight),
        "total_value": _clean_number(total_value),
    }


def _safe_var_name(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)


def _numeric_scale(values: list[float]) -> int:
    """Find a decimal scale so CP-SAT can handle decimal inputs as integers."""
    max_decimal_places = 0
    for value in values:
        text = f"{value:.10f}".rstrip("0").rstrip(".")
        if "." in text:
            max_decimal_places = max(max_decimal_places, len(text.split(".")[1]))
    return 10**max_decimal_places


def _to_int(value: float, scale: int) -> int:
    return int(round(value * scale))


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value
