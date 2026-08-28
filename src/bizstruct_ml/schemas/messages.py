from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from bizstruct_ml.generators.registry import GENERATORS

# Derived from the generator registry so this can't drift from what the
# worker can actually generate. `validate_model` is a special non-generation
# message handled separately in handler.py, not a block in the chain.
KNOWN_BLOCKS = frozenset(GENERATORS.keys()) | {"validate_model"}


class QueueMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    block: str
    payload: dict[str, Any] | None = None
    # False (default): normal chain progression — idempotency applies, a
    # block that's already generated is treated as already_generated and
    # skipped. True: an explicit regeneration request (e.g. models_options'
    # "regenerate" action) — idempotency is bypassed even if the block
    # already has data, since that's the whole point of asking for it again.
    force: bool = False
    # Language to generate this block in ("uk"/"en") — the project's own
    # setting (bizstruct-be's `translation_key`), threaded through here so
    # it's known before the project fetch and can go straight into the
    # Langfuse trace's metadata/tags at span-open time. The generators
    # themselves still read language off the fetched ProjectState (see
    # llm/prompts/*.py) — this field exists for early trace attribution,
    # not as a second source of truth for prompt building.
    language: str = "en"


class HookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    block: str
    status: Literal["success", "failed"]
    data: dict[str, Any] | None = None
    error: str | None = None


class PubSubEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["block_generated"] = "block_generated"
    project_id: str
    block: str
    status: Literal["success", "failed"]
