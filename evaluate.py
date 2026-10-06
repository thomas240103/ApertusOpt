"""Check reference problems offline, or benchmark real Apertus responses."""

from __future__ import annotations

import argparse
import json
import os
from time import perf_counter

import requests

from main import PROJECT_ROOT, build_prompt
from src.apertus_client import ApertusClient
from src.evaluator import evaluate_case


def main() -> None:
    cases = json.loads(
        (PROJECT_ROOT / "problems" / "knapsack_cases.json").read_text(encoding="utf-8")
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the real Apertus API.")
    parser.add_argument("--case", choices=[case["id"] for case in cases])
    args = parser.parse_args()
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]

    client = None
    if args.live:
        client = ApertusClient.from_env()
        if os.getenv("MOCK_APERTUS", "").lower() == "true":
            parser.error("Set MOCK_APERTUS=false before using --live.")
        if not client.api_url or not client.api_key or not client.api_key.strip():
            parser.error("Set APERTUS_API_URL and APERTUS_API_KEY in .env for --live.")
        if not client.model:
            parser.error("Set APERTUS_MODEL in .env for --live.")

    results = []
    for case in cases:
        if not args.live and "expected_error_terms" in case:
            results.append({"id": case["id"], "skipped": True,
                            "reason": "Requires a real Apertus response; run --live."})
            continue
        started = perf_counter()
        if client is not None:
            try:
                raw_response = client.generate(build_prompt(case["text"]))
            except (requests.RequestException, ValueError) as exc:
                # Keep credentials and provider response bodies out of reports.
                results.append({"id": case["id"], "passed": False,
                                "api_error": type(exc).__name__})
                continue
        else:
            raw_response = json.dumps(case["expected_problem"])
        result = evaluate_case(case, raw_response)
        result["elapsed_seconds"] = round(perf_counter() - started, 3)
        if args.live:
            result["raw_response"] = raw_response
        results.append(result)

    passed = sum(result.get("passed") is True for result in results)
    failed = sum(result.get("passed") is False for result in results)
    report = {
        "mode": "live" if args.live else "offline_reference",
        "apertus_tested": args.live and any(
            isinstance(result.get("raw_response"), str) for result in results
        ),
        "model": client.model if client else None,
        "note": (
            "Live API run. Responses are checked against references; API errors fail."
            if args.live else
            "Only reference JSON and solver tested. No LLM calls or extraction measured."
        ),
        "passed": passed,
        "failed": failed,
        "skipped": sum(result.get("skipped", False) for result in results),
        "results": results,
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
