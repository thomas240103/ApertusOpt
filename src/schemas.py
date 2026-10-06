"""Pydantic schemas for supported optimization problems."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnapsackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    weight: float = Field(..., gt=0)
    value: float

    @field_validator("weight", "value", mode="before")
    @classmethod
    def numbers_must_be_json_numbers(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("must be a JSON number")
        if not isfinite(value):
            raise ValueError("must be finite")
        return value

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("item name must not be blank")
        return stripped


class KnapsackProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_type: Literal["knapsack"]
    sense: Literal["maximize"]
    items: list[KnapsackItem] = Field(..., min_length=1)
    capacity: float = Field(..., gt=0)

    @field_validator("capacity", mode="before")
    @classmethod
    def capacity_must_be_json_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("capacity must be a JSON number")
        if not isfinite(value):
            raise ValueError("capacity must be finite")
        return value
