from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, FutureScenario, Stage, derive_artifact_id
from pydantic import BaseModel

from bizstruct_ml.core.context import gather_final
from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import future_scenario as prompt


class FutureScenarioGenerator(StageGenerator):
    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.FUTURE_SCENARIO

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        canvas, _ = gather_final(ctx.row, ctx.rows)
        scenario = FutureScenario.from_generated(
            generated, id=derive_artifact_id(ctx.row.id, ArtifactType.FUTURE_SCENARIO, 0), canvas_id=canvas.id
        )
        return [(ArtifactType.FUTURE_SCENARIO, scenario)]
