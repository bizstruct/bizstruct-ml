from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, EmpathyMap, Stage, derive_artifact_id
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import empathy_map as prompt


class EmpathyMapGenerator(StageGenerator):
    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.EMPATHY_MAP

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        empathy_map = EmpathyMap.from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.EMPATHY_MAP, 0),
            project_id=ctx.project_id,
        )
        return [(ArtifactType.EMPATHY_MAP, empathy_map)]
