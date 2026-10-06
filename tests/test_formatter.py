from unittest import TestCase

from src.formatter import format_knapsack_model
from src.schemas import KnapsackProblem


class TestKnapsackFormatter(TestCase):
    def test_formats_example_problem(self) -> None:
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

        formulation = format_knapsack_model(problem)

        self.assertIn("maximize", formulation)
        self.assertIn("10*A + 14*B + 7*C", formulation)
        self.assertIn("4*A + 6*B + 3*C <= 10", formulation)
        self.assertIn("A, B, C in {0, 1}", formulation)
