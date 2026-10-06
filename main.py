"""Command-line demonstration for ApertusOpt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.apertus_client import ApertusClient
from src.evaluator import evaluate_solution
from src.formatter import format_knapsack_model
from src.parser import parse_knapsack_response
from src.solver import solve_knapsack


PROJECT_ROOT = Path(__file__).resolve().parent

EXAMPLE_PROBLEM_TEXT = """I have a backpack with capacity 10 kg.

Item A weighs 4 kg and is worth 10.
Item B weighs 6 kg and is worth 14.
Item C weighs 3 kg and is worth 7.

Select the items that maximize total value without exceeding the capacity."""


def build_prompt(problem_text: str) -> str:
    prompt_template = (PROJECT_ROOT / "prompts" / "knapsack_prompt.txt").read_text(
        encoding="utf-8"
    )
    return prompt_template.replace("{{problem_text}}", problem_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ApertusOpt knapsack demo.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the built-in mock Apertus response instead of calling an API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mock:
        os.environ["MOCK_APERTUS"] = "true"

    prompt = build_prompt(EXAMPLE_PROBLEM_TEXT)
    client = ApertusClient.from_env()

    raw_json = client.generate(prompt)
    print("Generated JSON:")
    print(raw_json)

    problem = parse_knapsack_response(raw_json)
    print("\nMathematical formulation:")
    print(format_knapsack_model(problem))

    solution = solve_knapsack(problem)
    evaluation = evaluate_solution(problem, solution)

    print("\nSolution:")
    print(json.dumps(solution, indent=2))

    print("\nEvaluation:")
    print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()
