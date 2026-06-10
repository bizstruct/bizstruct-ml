from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WhatIfScenario(BaseModel):
    id: UUID
    vector: Literal["Financial", "Technical", "Emotional"]
    color: Literal["indigo", "teal", "slate"]
    icon: Literal["coins", "cpu", "heartHandshake"]
    title: str
    description: str
    value: str
    revenue: str
    status: Literal["applied", "draft"]


class WhatIf(BaseModel):
    scenarios: list[WhatIfScenario] = Field(min_length=3, max_length=3)
