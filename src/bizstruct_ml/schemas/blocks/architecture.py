from typing import Literal

from pydantic import BaseModel

EpicenterValue = Literal[
    "Finance-driven",
    "Customer-driven",
    "Offer-driven",
    "Resource-driven",
    "Competitor-driven",
]

PatternValue = Literal["FREE", "PAID", "OPEN", "Multi-sided Platform", "Long Tail"]


class Epicenter(BaseModel):
    value: EpicenterValue
    description: str
    status: Literal["determined"] = "determined"


class Pattern(BaseModel):
    value: PatternValue
    subtype: str
    description: str
    status: Literal["system_selection"] = "system_selection"


class ArchLocale(BaseModel):
    epicenter: Epicenter
    pattern: Pattern


class Architecture(BaseModel):
    uk: ArchLocale
    en: ArchLocale
