"""Patterns generator. All Patterns logic (aliases, NetScore structure, group ids) is here and in
the prompt and `patterns_validation`, so it can be replaced when NetScore moves into the domain."""

import uuid
from typing import ClassVar

from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    ArtifactType,
    PatternsGenerated,
    Stage,
    derive_artifact_id,
    patterns_from_generated,
)
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator
from bizstruct_ml.llm.prompts import patterns as prompt
from bizstruct_ml.stages.patterns_validation import validate_patterns_structure


def group_id(row_id: str, position: int) -> str:
    """Deterministic id of the group at `position` in Patterns.groups: regeneration keeps foreign keys valid."""
    return str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{row_id}:group:{position}"))


class PatternsGenerator(StageGenerator):
    prompt_version: ClassVar[str] = prompt.PROMPT_VERSION
    stage: ClassVar[Stage] = Stage.PATTERNS

    def build_messages(self, ctx: StageContext) -> list[dict]:
        return prompt.build_messages(ctx)

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        assert isinstance(generated, PatternsGenerated)
        segments = prompt.segments_of(ctx)
        aliases = [s.alias for s in segments]
        validate_patterns_structure(
            aliases,
            [
                (p.segment_pair.segment_alias_a, p.segment_pair.segment_alias_b, p.synergy, p.conflict)
                for p in generated.pairwise_scores
            ],
            [g.segment_aliases for g in generated.groups],
        )
        generated = _canonical_order(generated, aliases)
        patterns = patterns_from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.PATTERNS, 0),
            project_id=ctx.project_id,
            segment_ids={s.alias: s.empathy_map.id for s in segments},
            group_ids=[group_id(ctx.row.id, i) for i in range(len(generated.groups))],
        )
        return [(ArtifactType.PATTERNS, patterns)]


def _canonical_order(generated: PatternsGenerated, aliases: list[str]) -> PatternsGenerated:
    """Groups by their lowest alias, aliases ascending inside a group: the group at position i, and so the
    canvas row with instance_index i, does not depend on the order the model happened to write."""
    order = {alias: i for i, alias in enumerate(aliases)}
    groups = [g.model_copy(update={"segment_aliases": sorted(g.segment_aliases, key=order.__getitem__)}) for g in generated.groups]
    groups.sort(key=lambda g: order[g.segment_aliases[0]])
    return generated.model_copy(update={"groups": groups})
