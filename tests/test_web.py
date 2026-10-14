"""Local API and verified presentation regression tests; no live API calls."""

import json
import http.client
import os
import threading
import unittest
from unittest.mock import patch

import requests

from src.apertus_client import MOCK_PALLET_RESPONSE
from src.presentation import optimize_pallets
from src.schemas import KnapsackProblem
from src.solver import solve_knapsack
from web_app import create_server, extract_problem


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MOCK_PALLET_RESPONSE)

    def test_summary_and_totals(self):
        result = optimize_pallets(self.data)
        self.assertEqual(result["solution"]["selected_items"], ["B", "C", "D"])
        self.assertIn("EUR 700.00", result["summary"])
        self.assertEqual(result["remaining_weight"], 1000)
        self.assertEqual(result["remaining_volume"], 1)
        self.assertEqual(result["excluded_items"], ["A", "E"])
        self.assertTrue(result["evaluation"]["is_feasible"])

    def test_changed_capacity_recalculates(self):
        self.data["volume_capacity"] = 30
        result = optimize_pallets(self.data)
        self.assertEqual(result["solution"]["total_value"], 780)
        self.assertEqual(result["solution"]["selected_items"], ["A", "B", "D"])

    def test_empty_selection_is_valid(self):
        self.data["capacity"] = 1
        self.assertIn("Load no pallets.", optimize_pallets(self.data)["summary"])

    def test_feasible_is_not_claimed_optimal(self):
        solution = solve_knapsack(KnapsackProblem.model_validate(self.data))
        solution["status"] = "FEASIBLE"
        with patch("src.presentation.solve_knapsack", return_value=solution):
            self.assertIn("optimality was not proven", optimize_pallets(self.data)["summary"])

    def test_unverified_result_is_rejected(self):
        for solution in ({"status": "UNKNOWN"}, {"status": "OPTIMAL", "selected_items": ["A"],
                         "total_weight": 0, "total_volume": 0, "total_value": 100}):
            with patch("src.presentation.solve_knapsack", return_value=solution):
                with self.assertRaises(ValueError):
                    optimize_pallets(self.data)

    def test_volume_required(self):
        self.data.pop("volume_capacity")
        for item in self.data["items"]:
            item.pop("volume")
        with self.assertRaises(ValueError):
            optimize_pallets(self.data)

    def test_limit_is_validated(self):
        problem = KnapsackProblem.model_validate(self.data)
        for limit in (0, -1, float("nan"), 301):
            with self.assertRaises(ValueError):
                solve_knapsack(problem, time_limit=limit)

    def test_demo_has_no_network_and_does_not_mutate_env(self):
        with patch.dict(os.environ, {"MOCK_APERTUS": "false"}), patch("requests.post") as post:
            result = extract_problem({"text": "Different data", "mode": "demo"})
            self.assertEqual(result["problem"], self.data)
            self.assertEqual(os.environ["MOCK_APERTUS"], "false")
            post.assert_not_called()

    def test_live_mock_guard_and_sanitized_provider_errors(self):
        with patch.dict(os.environ, {"MOCK_APERTUS": "true"}):
            with self.assertRaisesRegex(ValueError, "disabled"):
                extract_problem({"text": "Truck", "mode": "live"})
        with patch.dict(os.environ, {"MOCK_APERTUS": "false"}), patch("web_app.ApertusClient.from_env") as factory:
            factory.return_value.api_url = "https://example.invalid"
            factory.return_value.generate.side_effect = requests.RequestException("SECRET")
            with self.assertRaises(ValueError) as error:
                extract_problem({"text": "Truck", "mode": "live"})
            self.assertNotIn("SECRET", str(error.exception))

    def test_invalid_extractions_are_rejected(self):
        for data in ({"text": "", "mode": "demo"}, {"text": "x", "mode": "other"}):
            with self.assertRaises(ValueError):
                extract_problem(data)
        with patch.dict(os.environ, {"MOCK_APERTUS": "false"}), patch("web_app.ApertusClient.from_env") as factory:
            factory.return_value.generate.return_value = '{"error":"secret provider details"}'
            with self.assertRaises(ValueError) as error:
                extract_problem({"text": "Truck", "mode": "live"})
            self.assertNotIn("secret", str(error.exception))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.session = requests.Session()
        cls.session.trust_env = False

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.session.close()

    def post(self, path, data, **kwargs):
        return self.session.post(self.url + path, json=data, headers={"X-ApertusOpt": "1", **kwargs}, timeout=20)

    def test_static_and_no_secret_files(self):
        for path in ("/", "/app.js", "/style.css", "/api/example"):
            response = self.session.get(self.url + path, timeout=5)
            self.assertEqual(response.status_code, 200)
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for path in ("/.env", "/src/solver.py", "/../.env"):
            self.assertEqual(self.session.get(self.url + path, timeout=5).status_code, 404)

    def test_extract_edit_solve(self):
        extraction = self.post("/api/extract", {"text": "example", "mode": "demo"})
        self.assertEqual(extraction.status_code, 200)
        data = extraction.json()["problem"]
        data["volume_capacity"] = 30
        response = self.post("/api/solve", data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["solution"]["total_value"], 780)

    def test_bad_data(self):
        data = json.loads(MOCK_PALLET_RESPONSE)
        data["capacity"] = -10
        response = self.post("/api/solve", data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("capacity", response.json()["error"])
        self.assertEqual(self.post("/api/solve", []).status_code, 400)

    def test_cross_origin_and_dns_rebinding_rejected(self):
        self.assertEqual(self.post("/api/solve", {}, Origin="https://untrusted.invalid").status_code, 403)
        self.assertEqual(self.post("/api/solve", {}, Host="untrusted.invalid").status_code, 403)
        self.assertEqual(self.session.post(self.url + "/api/solve", json={}, timeout=5).status_code, 403)

    def test_busy_response(self):
        self.server.work_lock.acquire()
        try:
            self.assertEqual(self.post("/api/solve", {}).status_code, 429)
        finally:
            self.server.work_lock.release()

    def test_oversized_request(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.putrequest("POST", "/api/extract")
            connection.putheader("Content-Length", "256001")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("X-ApertusOpt", "1")
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 413)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
