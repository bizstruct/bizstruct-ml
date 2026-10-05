"""Run one stage row: generate, convert, check consistency, retry inside the message.

Knows nothing about queues, HTTP or Service Bus. A `StageGenerator` supplies the
stage-specific parts (prompt, conversion to persisted artifacts); the runner owns
the loop around it:

1. build the context from the row's refs and ask the LLM for the stage's
   generation contract;
2. convert with the persisted model's `from_generated` (the generator derives ids
   with `derive_artifact_id`; the LLM never writes an id);
3. run the deterministic rules; if any is an error, regenerate with the violation
   messages as feedback, at most `MAX_CONSISTENCY_RETRIES` times. Warnings never
   retry;
4. run the judge checks once on the final artifacts (advisory, see
   `bizstruct_ml.judge.base.JUDGE_BLOCKING`) and build the report.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import ClassVar, Protocol

import structlog
from bizstruct_domain.schemas import (
    CONSISTENCY_RULES,
    GENERATION_CONTRACTS,
    JUDGE_CHECKS,
    ArtifactRecord,
    ArtifactType,
    ConsistencyReport,
    ConsistencyRule,
    JudgeCheck,
    ProjectSnapshot,
    Stage,
    StageErrorCode,
    StageFailure,
    StageRow,
    parse_artifact,
)
from pydantic import BaseModel, ConfigDict

from bizstruct_ml.core.consistency import build_report, run_deterministic, run_judge
from bizstruct_ml.core.context import ContextError, gather_context, rows_by_id
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.llm.client import LLMError
from bizstruct_ml.llm.retry import retry_async
from bizstruct_ml.observability import tracing

log = structlog.get_logger()

MAX_CONSISTENCY_RETRIES = 2
_MAX_FAILURE_MESSAGE = 2000


class StructuredLLM(Protocol):
    """What the runner needs from the generator client (`LLMClient` fits)."""

    @property
    def model_name(self) -> str: ...

    last_usage: dict[str, int] | None

    async def generate_structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel: ...


class StageContext(BaseModel):
    """Everything a generator may read for one row."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_id: str
    idea: str
    language: str
    row: StageRow
    # Artifacts of the rows in row.refs, labelled by stage.
    artifacts: dict[Stage, list[BaseModel]]


class StageGenerator(ABC):
    """Stage-specific half of generation. One subclass per stage."""

    stage: ClassVar[Stage]

    @abstractmethod
    def build_messages(self, ctx: StageContext) -> list[dict]:
        """Chat messages asking for `GENERATION_CONTRACTS[stage]`."""

    @abstractmethod
    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        """Convert the LLM output to persisted artifacts with derived ids.

        Raise a pydantic `ValidationError` if the content does not fit.
        """


class RunOutcome(BaseModel):
    artifacts: list[ArtifactRecord] = []
    consistency: ConsistencyReport | None = None
    failure: StageFailure | None = None
    # How many times the row was regenerated because of consistency errors.
    consistency_retries: int = 0

    @property
    def success(self) -> bool:
        return self.failure is None


def _feedback_message(messages: Sequence[str]) -> dict:
    bullets = "\n".join(f"- {m}" for m in messages)
    return {
        "role": "user",
        "content": "Your previous answer was inconsistent with the other artifacts of this project. "
        f"Fix these problems and answer again:\n{bullets}",
    }


class StageRunner:
    def __init__(
        self,
        generators: Mapping[Stage, StageGenerator],
        llm: StructuredLLM,
        judge: ConsistencyJudge,
        *,
        rules: Sequence[ConsistencyRule] = CONSISTENCY_RULES,
        checks: Sequence[JudgeCheck] = JUDGE_CHECKS,
        retry_wait: float = 2.0,
    ) -> None:
        for stage, generator in generators.items():
            contracts = GENERATION_CONTRACTS.get(stage, ())
            if generator.stage != stage or len(contracts) != 1:
                raise ValueError(
                    f"generator for {stage.value} must declare that stage and the stage must have exactly "
                    f"one generation contract (got {len(contracts)}); multi-contract stages come with the cycle"
                )
        self._generators = dict(generators)
        self._llm = llm
        self._judge = judge
        self._rules = rules
        self._checks = checks
        self._retry_wait = retry_wait

    def has_generator(self, stage: Stage) -> bool:
        return stage in self._generators

    async def run(self, row: StageRow, snapshot_closure: ProjectSnapshot, language: str) -> RunOutcome:
        generator = self._generators[row.stage]
        rows = rows_by_id(snapshot_closure.rows)
        try:
            ctx = StageContext(
                project_id=snapshot_closure.project_id,
                idea=snapshot_closure.idea,
                language=language,
                row=row,
                artifacts=gather_context(row, rows),
            )
        except ContextError as e:
            return self._failed(f"context: {e}")

        contract = GENERATION_CONTRACTS[row.stage][0]
        feedback: list[str] = []
        retries = 0
        while True:
            try:
                models = await self._generate(generator, ctx, contract, feedback, retries)
            except (LLMError, ValueError) as e:
                return self._failed(str(e))

            with tracing.span("consistency_rules"):
                violations = run_deterministic(row, [m for _, m in models], rows, self._rules)
            errors = [v.message for v in violations if v.severity == "error"]
            if not errors or retries >= MAX_CONSISTENCY_RETRIES:
                break
            retries += 1
            feedback = errors
            log.info("consistency_retry", row_id=row.id, stage=row.stage.value, retry=retries, errors=len(errors))

        fresh = [m for _, m in models]
        reports, unavailable = await run_judge(row, fresh, rows, self._judge, self._checks)
        return RunOutcome(
            artifacts=[
                ArtifactRecord(id=m.id, type=t, data=m.model_dump(mode="json"))  # type: ignore[attr-defined]
                for t, m in models
            ],
            consistency=build_report(violations, reports, unavailable),
            consistency_retries=retries,
        )

    async def _generate(
        self,
        generator: StageGenerator,
        ctx: StageContext,
        contract: type,
        feedback: Sequence[str],
        consistency_round: int,
    ) -> list[tuple[ArtifactType, BaseModel]]:
        messages = generator.build_messages(ctx)
        if feedback:
            messages = [*messages, _feedback_message(feedback)]
        attempts = {"n": 0}

        async def attempt() -> list[tuple[ArtifactType, BaseModel]]:
            attempts["n"] += 1
            with tracing.generation_span(
                "llm_call",
                model=self._llm.model_name,
                input=messages,
                metadata={"attempt": attempts["n"], "consistency_round": consistency_round},
            ) as span:
                generated = await self._llm.generate_structured(messages, contract)
                span.update(output=generated.model_dump(mode="json"), usage_details=self._llm.last_usage)
            models = generator.to_artifacts(generated, ctx)
            if not models:
                raise ValueError(f"generator for {ctx.row.stage.value} produced no artifacts")
            # Validate what be will validate, so a bad artifact is a generation
            # failure here and not a 422 (and a dead-lettered message) there.
            for artifact_type, model in models:
                parse_artifact(
                    ArtifactRecord(id=model.id, type=artifact_type, data=model.model_dump(mode="json"))  # type: ignore[attr-defined]
                )
            return models

        return await retry_async(
            attempt,
            retry_on=(LLMError, ValueError),  # pydantic's ValidationError is a ValueError
            wait_min=self._retry_wait,
            wait_max=self._retry_wait,
        )

    @staticmethod
    def _failed(message: str) -> RunOutcome:
        return RunOutcome(
            failure=StageFailure(code=StageErrorCode.GENERATION_FAILED, message=message[:_MAX_FAILURE_MESSAGE])
        )
