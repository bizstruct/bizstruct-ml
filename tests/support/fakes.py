"""Shared test doubles: a scripted generator LLM and snapshot builders.

No network anywhere: the generator LLM is `FakeLLM`, the judge is
`bizstruct_ml.judge.fake.FakeJudgeModel`, the backend is an httpx MockTransport
or (from slice 1) the in-memory fake backend.
"""

from collections.abc import Callable
from typing import Any, ClassVar

from bizstruct_domain.schemas import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    EmpathyMap,
    EmpathyMapGenerated,
    ProjectSnapshot,
    Stage,
    StageRow,
    StageStatus,
    derive_artifact_id,
)
from pydantic import BaseModel

from bizstruct_ml.core.stage_runner import StageContext, StageGenerator

PROJECT_ID = "project_001"


class FakeLLM:
    """Replies with the scripted items in order (the last repeats): a model
    instance, an exception to raise, or a callable `(messages, schema) -> model`.
    Records every call."""

    model_name = "fake-llm"
    last_usage: dict[str, int] | None = None
    last_finish_reason: str | None = None

    def __init__(self, replies: list[BaseModel | Exception | Callable[[list[dict], type[BaseModel]], BaseModel]]) -> None:
        self._replies = replies
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        self.calls.append({"messages": messages, "schema": schema})
        item = self._replies[min(len(self.calls), len(self._replies)) - 1]
        self.last_finish_reason = getattr(item, "finish_reason", "stop") if isinstance(item, Exception) else "stop"
        if isinstance(item, Exception):
            raise item
        return item(messages, schema) if callable(item) else item


def empathy_generated(name: str = "Olena") -> EmpathyMapGenerated:
    return EmpathyMapGenerated(
        persona_name=name,
        persona_demographics="34, urban, two children",
        sees=["Delivery apps"],
        hears=["Friends praise farm boxes"],
        thinks_and_feels=["Worried about freshness"],
        says_and_does=["Orders groceries online"],
        pains=["Unreliable delivery windows"],
        gains=["Fresh local produce"],
    )


def brief_model() -> Brief:
    return Brief(
        idea_summary="Farm produce delivery",
        industry="Food",
        customer_segment_candidates=["Urban parents"],
        existing_resources=[],
        gaps=["Unknown delivery radius"],
    )


def brief_row(row_id: str = "row_brief") -> StageRow:
    brief = brief_model()
    return StageRow(
        id=row_id,
        stage=Stage.BRIEF,
        status=StageStatus.DONE,
        attempt_id="att_brief",
        artifacts=[
            ArtifactRecord(
                id=derive_artifact_id(row_id, ArtifactType.BRIEF),
                type=ArtifactType.BRIEF,
                data=brief.model_dump(mode="json"),
            )
        ],
    )


def empathy_row(row_id: str = "row_em_0", *, status: StageStatus = StageStatus.RUNNING, attempt_id: str | None = "att1") -> StageRow:
    return StageRow(
        id=row_id,
        stage=Stage.EMPATHY_MAP,
        status=status,
        attempt_id=attempt_id,
        refs={Stage.BRIEF: ["row_brief"]},
    )


def snapshot_for(row: StageRow, *others: StageRow) -> ProjectSnapshot:
    return ProjectSnapshot(project_id=PROJECT_ID, idea="Farm produce delivery", language="en", rows=[row, *others])


class EmpathyMapTestGenerator(StageGenerator):
    """Minimal empathy_map generator for the generic tests (slice 1 ships the real one)."""

    stage: ClassVar[Stage] = Stage.EMPATHY_MAP

    def build_messages(self, ctx: StageContext) -> list[dict]:
        brief = ctx.artifacts[Stage.BRIEF][0]
        return [
            {"role": "system", "content": "Write an empathy map."},
            {"role": "user", "content": brief.model_dump_json()},
        ]

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        empathy = EmpathyMap.from_generated(
            generated,
            id=derive_artifact_id(ctx.row.id, ArtifactType.EMPATHY_MAP, 0),
            project_id=ctx.project_id,
        )
        return [(ArtifactType.EMPATHY_MAP, empathy)]
