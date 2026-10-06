from unittest import TestCase

from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


class TestKnapsackSolver(TestCase):
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
