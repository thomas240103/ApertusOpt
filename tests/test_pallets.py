import copy
import io
import json
import os
import random
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

import evaluate
import main
from src.apertus_client import ApertusClient, MOCK_KNAPSACK_RESPONSE, MOCK_PALLET_RESPONSE
from src.evaluator import evaluate_case, evaluate_solution
from src.formatter import format_knapsack_model
from src.parser import ParseError, parse_knapsack_response
from src.schemas import KnapsackProblem
from src.solver import solve_knapsack


CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "problems" / "pallet_cases.json")
    .read_text(encoding="utf-8")
)
BY_ID = {case["id"]: case for case in CASES}


class TestPalletSchema(TestCase):
    def test_valid_pallet_and_legacy_schemas(self):
        self.assertEqual(parse_knapsack_response(MOCK_PALLET_RESPONSE, require_volume=True).volume_capacity, 25)
        self.assertIsNone(parse_knapsack_response(MOCK_KNAPSACK_RESPONSE).volume_capacity)

    def test_missing_volume_never_silently_becomes_weight_only(self):
        for remove_capacity, remove_volumes in ((True, False), (False, True), (True, True)):
            data = json.loads(MOCK_PALLET_RESPONSE)
            if remove_capacity:
                del data["volume_capacity"]
            if remove_volumes:
                for item in data["items"]:
                    del item["volume"]
            with self.subTest(capacity=remove_capacity, volumes=remove_volumes):
                with self.assertRaises(ParseError):
                    parse_knapsack_response(json.dumps(data), require_volume=True)

    def test_one_missing_pallet_volume_is_rejected(self):
        data = json.loads(MOCK_PALLET_RESPONSE)
        del data["items"][1]["volume"]
        with self.assertRaisesRegex(ParseError, "Missing volume for items: B"):
            parse_knapsack_response(json.dumps(data), require_volume=True)

    def test_invalid_volume_numbers_are_rejected(self):
        for invalid in (True, False, "2", None, 0, -1, float("inf"), float("nan")):
            for location in ("volume", "volume_capacity"):
                data = json.loads(MOCK_PALLET_RESPONSE)
                if location == "volume":
                    data["items"][0][location] = invalid
                else:
                    data[location] = invalid
                with self.subTest(value=invalid, field=location):
                    with self.assertRaises(ValidationError):
                        KnapsackProblem.model_validate(data)

    def test_duplicate_names_and_extra_fields_are_rejected(self):
        data = json.loads(MOCK_PALLET_RESPONSE)
        data["items"][1]["name"] = " A "
        with self.assertRaisesRegex(ValidationError, "unique"):
            KnapsackProblem.model_validate(data)
        data = json.loads(MOCK_PALLET_RESPONSE)
        data["items"][0]["quantity"] = 2
        with self.assertRaises(ValidationError):
            KnapsackProblem.model_validate(data)

    def test_missing_data_error_is_readable(self):
        with self.assertRaisesRegex(ParseError, "Missing volume for B"):
            parse_knapsack_response('{"error": "Missing volume for B"}', require_volume=True)


class TestPalletSolver(TestCase):
    def test_reference_optima_against_exhaustive_enumeration(self):
        for case in CASES:
            if "expected_problem" not in case:
                continue
            with self.subTest(case=case["id"]):
                problem = KnapsackProblem.model_validate(case["expected_problem"])
                solution = solve_knapsack(problem)
                self.assertTrue(evaluate_case(case, json.dumps(case["expected_problem"]))["passed"])
                feasible = []
                for count in range(len(problem.items) + 1):
                    for subset in combinations(problem.items, count):
                        weight = sum(Decimal(str(item.weight)) for item in subset)
                        volume = sum(Decimal(str(item.volume)) for item in subset)
                        if weight <= Decimal(str(problem.capacity)) and volume <= Decimal(str(problem.volume_capacity)):
                            feasible.append(sum(Decimal(str(item.value)) for item in subset))
                self.assertEqual(Decimal(str(solution["total_value"])), max(feasible))

    def test_volume_changes_the_weight_only_optimum(self):
        data = json.loads(MOCK_PALLET_RESPONSE)
        full = solve_knapsack(KnapsackProblem.model_validate(data))
        self.assertEqual(set(full["selected_items"]), {"B", "C", "D"})
        self.assertEqual(full["total_value"], 700)
        del data["volume_capacity"]
        for item in data["items"]:
            del item["volume"]
        weight_only = solve_knapsack(KnapsackProblem.model_validate(data))
        self.assertEqual(set(weight_only["selected_items"]), {"A", "B", "D"})
        self.assertEqual(weight_only["total_value"], 780)
        self.assertNotIn("total_volume", weight_only)

    def test_unprofitable_pallets_can_be_left_out(self):
        data = json.loads(MOCK_PALLET_RESPONSE)
        for item in data["items"]:
            item["value"] = -1
        solution = solve_knapsack(KnapsackProblem.model_validate(data))
        self.assertEqual(solution["selected_items"], [])
        self.assertEqual(solution["total_value"], 0)
        self.assertEqual(solution["total_volume"], 0)

    def test_decimal_boundary_and_totals(self):
        problem = KnapsackProblem.model_validate(BY_ID["decimal_names"]["expected_problem"])
        solution = solve_knapsack(problem)
        self.assertEqual(solution["total_volume"], 0.3)
        self.assertEqual(solution["total_value"], 30.3)
        self.assertTrue(evaluate_solution(problem, solution)["is_feasible"])
        self.assertTrue(evaluate_solution(problem, solution)["reported_total_value_matches"])

    def test_unsafe_precision_or_scale_is_rejected_not_rounded(self):
        for volume in (0.00000000001, 1e20):
            data = json.loads(MOCK_PALLET_RESPONSE)
            data["items"][0]["volume"] = volume
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                solve_knapsack(KnapsackProblem.model_validate(data))

    def test_generated_small_cases_match_an_independent_oracle(self):
        rng = random.Random(42)
        for case_index in range(30):
            data = {
                "problem_type": "knapsack", "sense": "maximize",
                "capacity": rng.randint(1, 15), "volume_capacity": rng.randint(1, 15),
                "items": [{"name": str(i), "weight": rng.randint(1, 10),
                           "volume": rng.randint(1, 10), "value": rng.randint(-2, 20)}
                          for i in range(6)],
            }
            problem = KnapsackProblem.model_validate(data)
            solution = solve_knapsack(problem)
            best = max(
                sum(item["value"] for item in subset)
                for n in range(7) for subset in combinations(data["items"], n)
                if sum(item["weight"] for item in subset) <= data["capacity"]
                and sum(item["volume"] for item in subset) <= data["volume_capacity"]
            )
            with self.subTest(case=case_index):
                self.assertEqual(solution["status"], "OPTIMAL")
                self.assertEqual(solution["total_value"], best)
                self.assertTrue(evaluate_solution(problem, solution)["is_feasible"])


class TestPalletEvaluation(TestCase):
    def test_over_volume_and_duplicate_selections_are_not_feasible(self):
        problem = parse_knapsack_response(MOCK_PALLET_RESPONSE, require_volume=True)
        for names in (["A", "B", "D"], ["D", "D"], ["unknown"]):
            self.assertFalse(evaluate_solution(problem, {"status": "OPTIMAL", "selected_items": names})["is_feasible"])

    def test_unknown_solver_status_is_not_feasible(self):
        problem = parse_knapsack_response(MOCK_PALLET_RESPONSE)
        self.assertFalse(evaluate_solution(problem, {"status": "UNKNOWN", "selected_items": []})["is_feasible"])

    def test_reported_volume_is_checked(self):
        problem = parse_knapsack_response(MOCK_PALLET_RESPONSE)
        solution = solve_knapsack(problem)
        solution["total_volume"] = 1
        self.assertFalse(evaluate_solution(problem, solution)["reported_total_volume_matches"])

    def test_wrong_capacity_fails_even_with_the_same_selected_pallets(self):
        data = copy.deepcopy(BY_ID["truck_demo"]["expected_problem"])
        data["volume_capacity"] = 24
        result = evaluate_case(BY_ID["truck_demo"], json.dumps(data))
        self.assertTrue(result["solution_matches"])
        self.assertFalse(result["passed"])

    def test_missing_volume_errors_do_not_call_solver(self):
        with patch("src.evaluator.solve_knapsack") as solve:
            self.assertTrue(evaluate_case(BY_ID["missing_volume"], '{"error":"Missing volume for B"}')["passed"])
            self.assertFalse(evaluate_case(BY_ID["missing_volume"], '{"error":"Missing volume for A"}')["passed"])
            self.assertFalse(evaluate_case(BY_ID["truck_demo"], MOCK_KNAPSACK_RESPONSE)["passed"])
            solve.assert_not_called()

    def test_formatter_prints_both_constraints(self):
        text = format_knapsack_model(parse_knapsack_response(MOCK_PALLET_RESPONSE))
        self.assertIn("4000*A + 3500*B + 3000*C + 2500*D + 2000*E <= 10000", text)
        self.assertIn("12*A + 10*B + 8*C + 6*D + 5*E <= 25", text)

    def test_missing_truck_volume_accepts_exact_schema_field_name(self):
        with patch("src.evaluator.solve_knapsack") as solve:
            result = evaluate_case(BY_ID["missing_truck_space"], '{"error":"Missing volume_capacity for truck"}')
            self.assertTrue(result["passed"])
            solve.assert_not_called()

    def test_extra_error_fields_are_rejected(self):
        raw = '{"error":"missing_field", "field":"volume", "affected_pallet":"B"}'
        self.assertFalse(evaluate_case(BY_ID["missing_volume"], raw)["passed"])


class TestPalletCommands(TestCase):
    def test_mock_demo_works_without_api(self):
        with patch("sys.argv", ["main.py", "--pallets", "--mock"]), \
             patch.dict(os.environ, {"MOCK_APERTUS": "false"}), \
             patch("src.apertus_client.requests.post") as post, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            main.main()
            post.assert_not_called()
        text = output.getvalue()
        self.assertIn('"total_profit_eur": 700', text)
        self.assertIn('"total_volume_m3": 24', text)
        self.assertIn("MOCK MODE", text)

    def test_custom_text_is_in_the_pallet_prompt(self):
        text = "A new truck with different capacities."
        prompt = main.build_prompt(text, pallets=True)
        self.assertIn(text, prompt)
        self.assertIn('"volume_capacity"', prompt)
        self.assertNotIn("expected_solution", prompt)

    def test_custom_mock_input_does_not_pretend_to_be_live(self):
        with patch.dict(os.environ, {"MOCK_APERTUS": "true"}):
            client = ApertusClient.from_env(pallets=True)
            self.assertEqual(client.generate("Different problem"), MOCK_PALLET_RESPONSE)
            self.assertEqual(ApertusClient.from_env().generate("Different problem"), MOCK_KNAPSACK_RESPONSE)

    def test_offline_pallet_suite_is_separate_from_legacy_suite(self):
        with patch("sys.argv", ["evaluate.py", "--pallets"]), \
             patch("evaluate.ApertusClient.from_env") as create, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as result:
                evaluate.main()
            self.assertEqual(result.exception.code, 0)
            create.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertEqual(report["passed"], 5)
        self.assertEqual(report["skipped"], 2)
        self.assertFalse(report["apertus_tested"])

    def test_live_pallet_case_uses_pallet_prompt_without_reference_answers(self):
        with patch("sys.argv", ["evaluate.py", "--pallets", "--live", "--case", "truck_demo"]), \
             patch.dict(os.environ, {"MOCK_APERTUS": "false"}), \
             patch("evaluate.ApertusClient.from_env") as create, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            create.return_value.model = "test"
            create.return_value.generate.return_value = MOCK_PALLET_RESPONSE
            with self.assertRaises(SystemExit) as result:
                evaluate.main()
            self.assertEqual(result.exception.code, 0)
            prompt = create.return_value.generate.call_args.args[0]
            self.assertIn(BY_ID["truck_demo"]["text"], prompt)
            self.assertIn('"volume_capacity"', prompt)
            self.assertNotIn("expected_solution", prompt)
            self.assertNotIn("expected_problem", prompt)
        self.assertEqual(json.loads(output.getvalue())["passed"], 1)
