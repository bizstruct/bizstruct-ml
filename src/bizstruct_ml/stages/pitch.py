from typing import ClassVar

from bizstruct_domain.schemas import ArtifactType, Pitch, PitchGenerated, Stage, derive_artifact_id
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import pitch as prompt


class PitchGenerator(StageGenerator):
    """team_section and financial_analysis_section exist exactly when the matching row exists and is DONE. The prompt
    says so; the persisted model rejects a mismatch, and this generator turns it into a message the model can act on.
    business_case has no generator yet, so for now the financial section is always null (ml ADR-0001)."""

    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.PITCH

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        assert isinstance(generated, PitchGenerated)
        inputs = prompt.pitch_inputs(ctx)
        problems = []
        for section, value, present, source in (
            ("team_section", generated.team_section, inputs.team_info, "team information"),
            ("financial_analysis_section", generated.financial_analysis_section, inputs.business_case, "business case"),
        ):
            if present and not value:
                problems.append(f"{section} is required because there is a {source} for this project, but it is empty")
            if not present and value:
                problems.append(f"{section} must be null because there is no {source} for this project")
        if problems:
            raise ValueError("; ".join(problems) + ".")
        pitch = Pitch.from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.PITCH, 0),
            project_id=ctx.project_id,
            storytelling_id=inputs.storytelling.id,
            canvas_id=inputs.canvas.id,
            swot_id=inputs.swot.id,
            team_info_id=inputs.team_info.id if inputs.team_info else None,
            business_case_id=inputs.business_case.id if inputs.business_case else None,
        )
        return [(ArtifactType.PITCH, pitch)]
