"""Reproducible solver-only timings; no model calls or accuracy claims."""

import json
import random
from time import perf_counter

from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


def main():
    results = []
    for count in (50, 100, 500):
        rng = random.Random(42 + count)
        items = [{"name": f"P{i}", "weight": rng.randint(100, 1500),
                  "volume": rng.randint(1, 12), "value": rng.randint(20, 600)} for i in range(count)]
        problem = KnapsackProblem.model_validate({"problem_type": "knapsack", "sense": "maximize",
            "capacity": sum(i["weight"] for i in items) // 3,
            "volume_capacity": sum(i["volume"] for i in items) // 3, "items": items})
        start = perf_counter()
        result = solve_knapsack(problem, time_limit=10)
        results.append({"pallets": count, "seconds": round(perf_counter() - start, 4),
                        "status": result["status"], "total_margin": result["total_value"]})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
