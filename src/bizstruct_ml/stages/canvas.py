import uuid
from collections.abc import Callable
from itertools import count
from typing import ClassVar

from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    ArtifactType,
    Canvas,
    CanvasGenerated,
    Stage,
    derive_artifact_id,
)
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import canvas as prompt


def card_id_factory(canvas_id: str) -> Callable[[], str]:
    """Ids of the cards of one canvas: uuid5 of `<canvas id>:card:<n>`, n counting from 0 in the order
    `Canvas.from_generated` asks for them (section order, then card order). The id of a card depends on
    its position only, never on its text, so regenerating the canvas keeps every foreign key valid."""
    numbers = count()
    return lambda: str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{canvas_id}:card:{next(numbers)}"))


class CanvasGenerator(StageGenerator):
    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.CANVAS

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        assert isinstance(generated, CanvasGenerated)
        inputs = prompt.group_inputs(ctx)
        canvas_id = derive_artifact_id(ctx.row.id, ArtifactType.CANVAS, 1)
        canvas = Canvas.from_generated(
            generated,
            id=canvas_id,
            group_id=inputs.group.id,
            empathy_map_ids=list(inputs.group.empathy_map_ids),
            version=1,
            previous_version_id=None,
            new_card_id=card_id_factory(canvas_id),
        )
        return [(ArtifactType.CANVAS, canvas)]
