"""OR-Tools solver for the 0/1 knapsack MVP."""

from __future__ import annotations

from decimal import Decimal
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

    capacity, *weights = _scaled_integers(
        [problem.capacity] + [item.weight for item in problem.items]
    )
    values = _scaled_integers([item.value for item in problem.items])

    model.add(sum(weights[i] * selected[i] for i in range(len(selected))) <= capacity)
    if problem.volume_capacity is not None:
        volume_capacity, *volumes = _scaled_integers(
            [problem.volume_capacity] + [item.volume for item in problem.items]
        )
        model.add(sum(volumes[i] * selected[i] for i in range(len(selected))) <= volume_capacity)
    model.maximize(sum(values[i] * selected[i] for i in range(len(selected))))

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    chosen = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = [
            item for item, variable in zip(problem.items, selected) if solver.value(variable)
        ]
    result = {
        "status": solver.status_name(status),
        "selected_items": [item.name for item in chosen],
        "total_weight": _total([item.weight for item in chosen]),
        "total_value": _total([item.value for item in chosen]),
    }
    if problem.volume_capacity is not None:
        result["total_volume"] = _total([item.volume for item in chosen])
    return result


def _safe_var_name(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)


def _scaled_integers(values: list[float]) -> list[int]:
    """Scale each constraint separately; never silently round away a limit."""
    decimals = [Decimal(str(value)) for value in values]
    places = max(0, max(-value.as_tuple().exponent for value in decimals))
    if places > 10:
        raise ValueError("At most 10 decimal places are supported by the solver.")
    integers = [int(value * 10**places) for value in decimals]
    if sum(abs(value) for value in integers) > (1 << 62) - 1:
        raise ValueError("Scaled numbers are too large for the integer solver.")
    return integers


def _total(values: list[float]) -> int | float:
    total = sum((Decimal(str(value)) for value in values), Decimal(0))
    return int(total) if total == total.to_integral_value() else float(total)
