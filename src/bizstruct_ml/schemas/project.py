from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


class ProjectState(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: UUID
    title: str
    idea: str
    status: str
    # The generation-language parameter ("uk"/"en"), fixed at project
    # creation (bizstruct-be's Project.language). NOT translation_key
    # below — that's an unrelated frontend i18n lookup key for demo
    # project titles, and was mistakenly used as a language source by
    # every prompt module in llm/prompts/ and by generators/base.py's
    # language validator until this fix (it always evaluated to "en"
    # since translation_key is null for every real, non-seed project).
    language: str = "en"
    translation_key: str | None = "en"

    @field_validator("language", mode="before")
    @classmethod
    def coerce_language(cls, v: object) -> str:
        return str(v) if v else "en"

    @field_validator("translation_key", mode="before")
    @classmethod
    def coerce_translation_key(cls, v: object) -> str:
        return str(v) if v else "en"
    models_options: dict[str, Any] | None = None
    canvas: dict[str, Any] | None = None
    empathy_map: dict[str, Any] | None = None
    hypotheses: dict[str, Any] | None = None
    pitch: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    what_if: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None

    def get_block(self, block: str) -> dict[str, Any] | None:
        return getattr(self, block, None)
