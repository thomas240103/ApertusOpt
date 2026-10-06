import json
from itertools import combinations
from pathlib import Path
from unittest import TestCase

from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


class TestKnapsackSolver(TestCase):
    def test_reference_cases_have_the_expected_optima(self) -> None:
        path = Path(__file__).resolve().parents[1] / "problems" / "knapsack_cases.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        for case in cases:
            if "expected_problem" not in case:
                continue
            with self.subTest(case=case["id"]):
                problem = KnapsackProblem.model_validate(case["expected_problem"])
                solution = solve_knapsack(problem)
                reference = case["expected_solution"]
                self.assertEqual(solution["status"], "OPTIMAL")
                self.assertEqual(sorted(solution["selected_items"]),
                                 sorted(reference["selected_items"]))
                self.assertEqual(solution["total_weight"], reference["total_weight"])
                self.assertEqual(solution["total_value"], reference["total_value"])

                # Exhaustive enumeration independently checks these small fixtures.
                feasible_values = [
                    sum(item.value for item in subset)
                    for size in range(len(problem.items) + 1)
                    for subset in combinations(problem.items, size)
                    if sum(item.weight for item in subset) <= problem.capacity
                ]
                self.assertEqual(reference["total_value"], max(feasible_values))

    def test_example_problem_selects_a_and_b(self) -> None:
        problem = KnapsackProblem.model_validate(
            {
                "problem_type": "knapsack",
                "sense": "maximize",
                "items": [
                    {"name": "A", "weight": 4, "value": 10},
                    {"name": "B", "weight": 6, "value": 14},
                    {"name": "C", "weight": 3, "value": 7},
                ],
                "capacity": 10,
            }
        )

        solution = solve_knapsack(problem)

        self.assertEqual(solution["status"], "OPTIMAL")
        self.assertEqual(set(solution["selected_items"]), {"A", "B"})
        self.assertEqual(solution["total_weight"], 10)
        self.assertEqual(solution["total_value"], 24)
