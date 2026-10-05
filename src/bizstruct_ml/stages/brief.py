from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, Brief, Stage
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import brief as prompt


class BriefGenerator(StageGenerator):
    stage: ClassVar[Stage] = Stage.BRIEF

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        # Brief is its own contract and has no system fields; the runner derives its record id.
        return [(ArtifactType.BRIEF, Brief.model_validate(generated.model_dump()))]
