"""Pydantic schemas for supported optimization problems."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KnapsackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    weight: float = Field(..., gt=0)
    value: float
    volume: float | None = Field(default=None, gt=0)

    @field_validator("weight", "value", "volume", mode="before")
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
    volume_capacity: float | None = Field(default=None, gt=0)

    @field_validator("capacity", "volume_capacity", mode="before")
    @classmethod
    def capacity_must_be_json_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("capacity must be a JSON number")
        if not isfinite(value):
            raise ValueError("capacity must be finite")
        return value

    @model_validator(mode="after")
    def check_items_and_volume(self) -> "KnapsackProblem":
        names = [item.name for item in self.items]
        if len(names) != len(set(names)):
            raise ValueError("item names must be unique")
        if self.volume_capacity is not None:
            missing = [item.name for item in self.items if item.volume is None]
            if missing:
                raise ValueError(f"Missing volume for items: {', '.join(missing)}")
        elif any(item.volume is not None for item in self.items):
            raise ValueError("volume_capacity is required when item volumes are supplied")
        return self
