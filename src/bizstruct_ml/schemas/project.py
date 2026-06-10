from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ProjectState(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: UUID
    title: str
    idea: str
    status: str
    translation_key: str = "en"
    models_options: dict[str, Any] | None = None
    canvas_data: dict[str, Any] | None = None
    empathy_map: dict[str, Any] | None = None
    hypotheses: dict[str, Any] | None = None
    pitch: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    what_if: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None

    def get_block(self, block: str) -> dict[str, Any] | None:
        return getattr(self, block, None)
