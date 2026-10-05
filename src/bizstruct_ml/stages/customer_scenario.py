from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, CustomerScenario, Stage, derive_artifact_id
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import customer_scenario as prompt


class CustomerScenarioGenerator(StageGenerator):
    stage: ClassVar[Stage] = Stage.CUSTOMER_SCENARIO

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        scenario = CustomerScenario.from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.CUSTOMER_SCENARIO, 0),
            empathy_map_id=prompt.own_empathy_map(ctx).id,
        )
        return [(ArtifactType.CUSTOMER_SCENARIO, scenario)]
