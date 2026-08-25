from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from bizstruct_ml.generators.registry import GENERATORS

# Derived from the generator registry so this can't drift from what the
# worker can actually generate. `validate_model` is a special non-generation
# message handled separately in handler.py, not a block in the chain.
KNOWN_BLOCKS = frozenset(GENERATORS.keys()) | {"validate_model"}


class QueueMessage(BaseModel):
    project_id: UUID
    block: str
    payload: dict[str, Any] | None = None


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
