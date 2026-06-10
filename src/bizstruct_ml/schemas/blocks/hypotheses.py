import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Hypothesis(BaseModel):
    id: str = Field(pattern=r"^H\d+\.\d+$")
    text: str
    category: Literal["Desirability", "Viability", "Feasibility"]
    quadrant: Literal["q1", "q2", "q3", "q4"]


class Hypotheses(BaseModel):
    hypotheses: list[Hypothesis] = Field(min_length=5)

    @field_validator("hypotheses")
    @classmethod
    def all_categories_present(cls, v: list[Hypothesis]) -> list[Hypothesis]:
        categories = {h.category for h in v}
        required = {"Desirability", "Viability", "Feasibility"}
        missing = required - categories
        if missing:
            raise ValueError(f"Missing hypotheses for categories: {missing}")
        return v
