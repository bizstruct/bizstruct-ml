from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BusinessModel(BaseModel):
    id: UUID
    name: str
    tagline: str
    description: str
    monetization: Literal["subscription", "transaction_fee", "retainer_plus_saas"]
    target_segment: str
    key_metric: str
    time_to_value: str
    score: int = Field(ge=0, le=100)


class ModelsOptions(BaseModel):
    models: list[BusinessModel] = Field(min_length=3, max_length=3)
    selected_id: UUID | None = None
