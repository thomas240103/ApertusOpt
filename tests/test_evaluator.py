import copy
import io
import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import requests

import evaluate
from src.apertus_client import ApertusClient, MOCK_KNAPSACK_RESPONSE
from src.evaluator import evaluate_case
from src.parser import ParseError, parse_knapsack_response


CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "problems" / "knapsack_cases.json")
    .read_text(encoding="utf-8")
)
BY_ID = {case["id"]: case for case in CASES}


class TestCaseEvaluation(TestCase):
    def test_reference_formulations_pass(self) -> None:
        for case in CASES:
            if "expected_problem" in case:
                with self.subTest(case=case["id"]):
                    result = evaluate_case(case, json.dumps(case["expected_problem"]))
                    self.assertTrue(result["passed"])

    def test_reordered_items_and_code_fences_are_accepted(self) -> None:
        data = copy.deepcopy(BY_ID["base"]["expected_problem"])
        data["items"].reverse()
        result = evaluate_case(BY_ID["base"], "```json\n" + json.dumps(data) + "\n```")
        self.assertTrue(result["passed"])

    def test_correct_optimum_does_not_hide_wrong_extraction(self) -> None:
        data = copy.deepcopy(BY_ID["base"]["expected_problem"])
        data["capacity"] = 11
        result = evaluate_case(BY_ID["base"], json.dumps(data))
        self.assertTrue(result["solution_matches"])
        self.assertFalse(result["formulation_matches"])
        self.assertFalse(result["passed"])

    def test_fixed_mock_fails_changed_capacity(self) -> None:
        self.assertFalse(evaluate_case(BY_ID["capacity_7"], MOCK_KNAPSACK_RESPONSE)["passed"])

    def test_non_text_provider_content_fails_without_crashing(self) -> None:
        for case_id in ("base", "missing_weight"):
            for content in (None, [], {"unexpected": "content"}):
                with self.subTest(case=case_id, content=content):
                    self.assertFalse(evaluate_case(BY_ID[case_id], content)["passed"])

    def test_missing_weight_requires_explicit_error_and_never_solves(self) -> None:
        with patch("src.evaluator.solve_knapsack") as solve:
            for message in ("Missing weight for item B.", "Manca il peso di B."):
                with self.subTest(message=message):
                    result = evaluate_case(BY_ID["missing_weight"], json.dumps({"error": message}))
                    self.assertTrue(result["passed"])
            solve.assert_not_called()

    def test_invalid_or_invented_answers_do_not_count_as_missing_data_detection(self) -> None:
        responses = [
            "not JSON", "{}", '{"error": ""}', '{"error": "Service unavailable"}',
            '{"error": "Missing weight for item A"}', MOCK_KNAPSACK_RESPONSE,
            '{"error": "Missing weight for B", "capacity": 10}',
        ]
        for raw in responses:
            with self.subTest(raw=raw):
                self.assertFalse(evaluate_case(BY_ID["missing_weight"], raw)["passed"])

    def test_missing_weight_in_model_is_rejected_by_validator(self) -> None:
        data = copy.deepcopy(BY_ID["base"]["expected_problem"])
        del data["items"][1]["weight"]
        with self.assertRaises(ParseError):
            parse_knapsack_response(json.dumps(data))

    def test_invalid_response_for_complete_problem_fails_without_solver(self) -> None:
        with patch("src.evaluator.solve_knapsack") as solve:
            for raw in ("not JSON", '{"error": "Missing weight for B"}', '{"capacity": 10}'):
                with self.subTest(raw=raw):
                    result = evaluate_case(BY_ID["base"], raw)
                    self.assertFalse(result["passed"])
                    self.assertFalse(result["schema_valid"])
            solve.assert_not_called()


class TestEvaluationCommand(TestCase):
    def run_command(self, *args: str) -> tuple[int, dict]:
        with patch("sys.argv", ["evaluate.py", *args]), patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as exit_result:
                evaluate.main()
        return exit_result.exception.code, json.loads(output.getvalue())

    def test_offline_run_does_not_call_api_or_claim_llm_success(self) -> None:
        with patch("evaluate.ApertusClient.from_env") as create_client:
            code, report = self.run_command()
            create_client.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "offline_reference")
        self.assertFalse(report["apertus_tested"])
        self.assertEqual(report["passed"], 7)
        self.assertEqual(report["skipped"], 1)

    def test_live_refuses_mock_mode_and_missing_credentials(self) -> None:
        for mock_mode, key in (("true", "test-key"), ("false", "")):
            with self.subTest(mock_mode=mock_mode, key=key):
                client = ApertusClient("https://example.invalid/v1/chat/completions", key, "test")
                with patch("sys.argv", ["evaluate.py", "--live"]), \
                     patch.dict(os.environ, {"MOCK_APERTUS": mock_mode}), \
                     patch("evaluate.ApertusClient.from_env", return_value=client), \
                     patch("src.apertus_client.requests.post") as post, \
                     patch("sys.stderr", new_callable=io.StringIO):
                    with self.assertRaises(SystemExit) as result:
                        evaluate.main()
                    self.assertEqual(result.exception.code, 2)
                    post.assert_not_called()

    def test_live_failure_is_nonzero_and_only_problem_text_is_sent(self) -> None:
        with patch.dict(os.environ, {"MOCK_APERTUS": "false"}), \
             patch("evaluate.ApertusClient.from_env") as create_client:
            create_client.return_value.model = "test"
            create_client.return_value.api_key = "test-key"
            create_client.return_value.generate.return_value = MOCK_KNAPSACK_RESPONSE
            code, report = self.run_command("--live", "--case", "capacity_7")
            sent_prompt = create_client.return_value.generate.call_args.args[0]
            self.assertIn(BY_ID["capacity_7"]["text"], sent_prompt)
            self.assertNotIn("expected_solution", sent_prompt)
            self.assertNotIn("expected_problem", sent_prompt)
        self.assertEqual(code, 1)
        self.assertEqual(report["failed"], 1)

    def test_api_failure_is_not_counted_as_correct_rejection(self) -> None:
        with patch.dict(os.environ, {"MOCK_APERTUS": "false"}), \
             patch("evaluate.ApertusClient.from_env") as create_client:
            create_client.return_value.model = "test"
            create_client.return_value.api_key = "test-key"
            create_client.return_value.generate.side_effect = requests.Timeout("private details")
            code, report = self.run_command("--live", "--case", "missing_weight")
        self.assertEqual(code, 1)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["results"][0]["api_error"], "Timeout")
        self.assertFalse(report["apertus_tested"])
        self.assertNotIn("private details", json.dumps(report))
