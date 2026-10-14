"""Verified, deterministic summaries; no extra LLM call."""

from decimal import Decimal
from time import perf_counter

from src.evaluator import evaluate_solution
from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


def optimize_pallets(data: dict) -> dict:
    problem = KnapsackProblem.model_validate(data)
    if problem.volume_capacity is None:
        raise ValueError("Truck volume and every pallet's volume are required.")
    if len(problem.items) > 500:
        raise ValueError("The web demo supports at most 500 pallets.")
    start = perf_counter()
    solution = solve_knapsack(problem, time_limit=10)
    elapsed = perf_counter() - start
    if solution["status"] not in ("OPTIMAL", "FEASIBLE"):
        raise ValueError(f"No verified solution returned ({solution['status']}). Try a smaller scenario.")
    checks = evaluate_solution(problem, solution)
    if not all(checks[key] for key in (
        "is_feasible", "reported_total_weight_matches", "reported_total_value_matches",
        "reported_total_volume_matches",
    )):
        raise ValueError("Solution verification failed. No load plan is available.")
    selected = set(solution["selected_items"])
    remaining_weight = float(Decimal(str(problem.capacity)) - Decimal(str(solution["total_weight"])))
    remaining_volume = float(Decimal(str(problem.volume_capacity)) - Decimal(str(solution["total_volume"])))
    names = ", ".join(solution["selected_items"])
    action = f"Load pallets {names}." if names else "Load no pallets."
    certainty = ("This is an optimal selection for the confirmed data."
                 if solution["status"] == "OPTIMAL" else
                 "This selection is feasible; optimality was not proven within the time limit.")
    summary = (
        f"{action} The total margin is EUR {solution['total_value']:,.2f}, "
        f"using {solution['total_weight']:g} of {problem.capacity:g} kg and "
        f"{solution['total_volume']:g} of {problem.volume_capacity:g} m3. "
        f"Remaining capacity: {remaining_weight:g} kg and {remaining_volume:g} m3. {certainty}"
    )
    return {
        "problem": problem.model_dump(exclude_none=True), "solution": solution,
        "evaluation": checks, "summary": summary, "solve_seconds": round(elapsed, 4),
        "excluded_items": [item.name for item in problem.items if item.name not in selected],
        "remaining_weight": remaining_weight, "remaining_volume": remaining_volume,
    }
