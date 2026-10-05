from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, Ideation, Stage, derive_artifact_id
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import customer_scenario as shared
from bizstruct_ml.llm.prompts import ideation as prompt


class IdeationGenerator(StageGenerator):
    stage: ClassVar[Stage] = Stage.IDEATION

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        ideation = Ideation.from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.IDEATION, 0),
            empathy_map_id=shared.own_empathy_map(ctx).id,
        )
        return [(ArtifactType.IDEATION, ideation)]
