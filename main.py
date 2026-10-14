"""Command-line demonstration for ApertusOpt."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

import requests

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


def build_prompt(problem_text: str, *, pallets: bool = False) -> str:
    filename = "pallet_prompt.txt" if pallets else "knapsack_prompt.txt"
    prompt_template = (PROJECT_ROOT / "prompts" / filename).read_text(
        encoding="utf-8"
    )
    return prompt_template.replace("{{problem_text}}", problem_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ApertusOpt knapsack demo.")
    parser.add_argument("--pallets", action="store_true",
                        help="Select whole pallets within weight (kg) and volume (m3) limits.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the built-in mock Apertus response instead of calling an API.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--text",
        help="Natural-language knapsack problem to parse and solve.",
    )
    input_group.add_argument(
        "--file",
        help="Path to a text file containing a natural-language knapsack problem.",
    )
    return parser.parse_args()


def load_problem_text(args: argparse.Namespace) -> str:
    if args.file:
        problem_path = Path(args.file)
        if not problem_path.is_absolute():
            problem_path = PROJECT_ROOT / problem_path
        try:
            problem_text = problem_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise SystemExit(f"Problem file not found: {problem_path}") from exc
    else:
        if args.text is not None:
            problem_text = args.text.strip()
        elif args.pallets:
            problem_text = (PROJECT_ROOT / "problems" / "pallet_loading.txt").read_text(encoding="utf-8")
        else:
            problem_text = EXAMPLE_PROBLEM_TEXT

    if not problem_text:
        raise SystemExit("Problem text is empty.")
    return problem_text


def main() -> None:
    args = parse_args()
    if args.mock:
        os.environ["MOCK_APERTUS"] = "true"

    problem_text = load_problem_text(args)
    prompt = build_prompt(problem_text, pallets=args.pallets)
    client = ApertusClient.from_env(pallets=args.pallets)

    print("Problem text:")
    print(problem_text)
    if os.getenv("MOCK_APERTUS", "").lower() == "true":
        print("\nMOCK MODE: fixed example response; custom input is not interpreted.")

    raw_json = client.generate(prompt)
    print("\nGenerated JSON:")
    print(raw_json)

    problem = parse_knapsack_response(raw_json, require_volume=args.pallets)
    print("\nMathematical formulation:")
    print(format_knapsack_model(problem))

    solution = solve_knapsack(problem)
    evaluation = evaluate_solution(problem, solution)

    print("\nSolution:")
    print(json.dumps(solution, indent=2))

    print("\nEvaluation:")
    print(json.dumps(evaluation, indent=2))
    if args.pallets and solution["status"] in ("OPTIMAL", "FEASIBLE"):
        print("\nPallet load summary:")
        print(json.dumps({
            "selected_pallets": solution["selected_items"],
            "total_weight_kg": solution["total_weight"],
            "total_volume_m3": solution["total_volume"],
            "total_profit_eur": solution["total_value"],
            "remaining_weight_kg": float(Decimal(str(problem.capacity)) - Decimal(str(solution["total_weight"]))),
            "remaining_volume_m3": float(Decimal(str(problem.volume_capacity)) - Decimal(str(solution["total_volume"]))),
        }, indent=2))
        print("Selection only: volume sums do not certify 3D fit, stacking or load safety.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        raise SystemExit(f"Apertus API request failed ({type(exc).__name__}).") from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
