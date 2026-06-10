from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

KNOWN_BLOCKS = frozenset({
    "models_options",
    "canvas_data",
    "empathy_map",
    "hypotheses",
    "pitch",
    "scenario",
    "what_if",
    "architecture",
})


class QueueMessage(BaseModel):
    project_id: UUID
    block: str


class HookPayload(BaseModel):
    project_id: UUID
    block: str
    status: Literal["success", "failed"]
    data: dict[str, Any] | None = None
    error: str | None = None


class PubSubEvent(BaseModel):
    type: Literal["block_generated"] = "block_generated"
    project_id: str
    block: str
    status: Literal["success", "failed"]
