from uuid import UUID

from pydantic import BaseModel, Field


class CanvasItem(BaseModel):
    id: UUID
    text: str
    is_ai_generated: bool


class CanvasSection(BaseModel):
    items: list[CanvasItem] = Field(min_length=2, max_length=4)


class CanvasData(BaseModel):
    key_partners: list[CanvasItem] = Field(min_length=2, max_length=4)
    key_activities: list[CanvasItem] = Field(min_length=2, max_length=4)
    key_resources: list[CanvasItem] = Field(min_length=2, max_length=4)
    value_propositions: list[CanvasItem] = Field(min_length=2, max_length=4)
    customer_relationships: list[CanvasItem] = Field(min_length=2, max_length=4)
    channels: list[CanvasItem] = Field(min_length=2, max_length=4)
    customer_segments: list[CanvasItem] = Field(min_length=2, max_length=4)
    cost_structure: list[CanvasItem] = Field(min_length=2, max_length=4)
    revenue_streams: list[CanvasItem] = Field(min_length=2, max_length=4)
