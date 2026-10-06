"""Client for generating optimization model JSON with Apertus."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


MOCK_KNAPSACK_RESPONSE = json.dumps(
    {
        "problem_type": "knapsack",
        "sense": "maximize",
        "items": [
            {"name": "A", "weight": 4, "value": 10},
            {"name": "B", "weight": 6, "value": 14},
            {"name": "C", "weight": 3, "value": 7},
        ],
        "capacity": 10,
    },
    indent=2,
)


@dataclass(frozen=True)
class ApertusClient:
    """Small OpenAI-compatible HTTP client for Apertus-style chat completions."""

    api_url: str
    api_key: str | None
    model: str
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "ApertusClient":
        load_dotenv()
        return cls(
            api_url=os.getenv("APERTUS_API_URL", "").strip(),
            api_key=os.getenv("APERTUS_API_KEY"),
            model=os.getenv("APERTUS_MODEL", "apertus").strip(),
        )

    def generate(self, prompt: str) -> str:
        """Generate raw text from Apertus, or a deterministic response in mock mode."""
        if os.getenv("MOCK_APERTUS", "").lower() == "true":
            return MOCK_KNAPSACK_RESPONSE

        if not self.api_url:
            raise ValueError(
                "APERTUS_API_URL is required unless MOCK_APERTUS=true is set."
            )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You convert natural-language optimization problems into "
                        "strict JSON schemas."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return self._extract_text(data)

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """Extract generated text from common OpenAI-compatible response shapes."""
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass

        try:
            return data["choices"][0]["text"]
        except (KeyError, IndexError, TypeError):
            pass

        if isinstance(data.get("output_text"), str):
            return data["output_text"]

        raise ValueError(f"Could not extract generated text from response: {data}")


def generate(prompt: str) -> str:
    """Convenience module-level API requested by the MVP."""
    return ApertusClient.from_env().generate(prompt)
