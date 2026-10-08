"""Storytelling generator (BMG, Design -> Storytelling).

The perspective, the goal and the format are choices of the STAGE, not content the model decides. The
methodology (step 10) gives no default for any of them. These are PROJECT RULES chosen by the maintainer
(ml ADR-0001), a controlled variable of the experiments: the same in every configuration, the future agent
included. They are stated in the prompt and any other value is a conversion error that retries with the message.
Making them a user choice is a later product decision.
"""

from typing import ClassVar

from bizstruct_domain.schemas import (
    ArtifactType,
    Stage,
    Storytelling,
    StorytellingFormat,
    StorytellingGenerated,
    StorytellingGoal,
    StorytellingPerspective,
    derive_artifact_id,
)
from pydantic import BaseModel

from bizstruct_ml.core.context import gather_final
from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import storytelling as prompt

PERSPECTIVE = StorytellingPerspective.CUSTOMER
GOAL = StorytellingGoal.PITCHING_INVESTORS
FORMAT = StorytellingFormat.TEXT_AND_IMAGE


def check_fixed_choices(generated: StorytellingGenerated) -> None:
    """Raise a `ValueError` naming every field that differs from the project's fixed value."""
    problems = [
        f"{name} must be '{fixed.value}' (fixed by the project for every story), got '{got.value}'"
        for name, fixed, got in (
            ("perspective", PERSPECTIVE, generated.perspective),
            ("goal", GOAL, generated.goal),
            ("format", FORMAT, generated.format),
        )
        if got != fixed
    ]
    if problems:
        raise ValueError("; ".join(problems) + ".")


class StorytellingGenerator(StageGenerator):
    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.STORYTELLING

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        assert isinstance(generated, StorytellingGenerated)
        check_fixed_choices(generated)
        canvas, _ = gather_final(ctx.row, ctx.rows)
        story = Storytelling.from_generated(
            generated, id=derive_artifact_id(ctx.row.id, ArtifactType.STORYTELLING, 0), canvas_id=canvas.id
        )
        return [(ArtifactType.STORYTELLING, story)]
