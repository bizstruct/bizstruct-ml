"""Run one stage row: generate, convert, check consistency, retry inside the message.

Knows nothing about queues, HTTP or Service Bus. A `StageGenerator` supplies the
stage-specific parts (prompt, conversion to persisted artifacts); the runner owns
the loop around it:

1. build the context from the row's refs and ask the LLM for the stage's
   generation contract;
2. check the text for degeneration; a retry-worthy finding retries like a schema
   error and fails the row once retries run out;
   convert with the persisted model's `from_generated` (the generator derives ids
   with `derive_artifact_id`; the LLM never writes an id);
3. run the deterministic rules; if any is an error, regenerate with the violation
   messages as feedback, at most `MAX_CONSISTENCY_RETRIES` times. Warnings never
   retry;
4. run the judge checks once on the final artifacts (advisory, see
   `bizstruct_ml.judge.base.JUDGE_BLOCKING`) and build the report.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from typing import ClassVar, Protocol, TypeVar

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
    derive_artifact_id,
    parse_artifact,
)
from pydantic import BaseModel, ConfigDict

from bizstruct_ml.core.consistency import build_report, run_deterministic, run_judge
from bizstruct_ml.core.context import ContextError, gather_closure, gather_context, rows_by_id
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.llm.client import LLMError, LLMLengthError
from bizstruct_ml.llm.retry import retry_async
from bizstruct_ml.observability import tracing
from bizstruct_ml.validation.degenerate_text import DegenerateTextError, validate_block_text

log = structlog.get_logger()

T = TypeVar("T")

MAX_CONSISTENCY_RETRIES = 2
# A cut-off completion (finish_reason "length") is retried once: the same prompt
# is unlikely to fit on a third try either, so the row fails with a clear message.
MAX_LENGTH_RETRIES = 1
_MAX_FAILURE_MESSAGE = 2000
_MAX_FEEDBACK_ERROR = 1500


class GenerationFailed(Exception):
    """Generation failed for a reason a retry will not fix; the row fails with this message."""


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
    # Artifacts of every row reachable through refs (transitively), labelled by stage.
    closure: dict[Stage, list[BaseModel]] = {}
    # The rows of the snapshot closure by id (for row facts such as `instance_index`).
    rows: dict[str, StageRow] = {}


class StageGenerator(ABC):
    """Stage-specific half of generation. One subclass per stage."""

    stage: ClassVar[Stage]
    # Version of the stage prompt text; bump it whenever the prompt changes. It goes
    # into the trace metadata so a result can be tied to the prompt that made it.
    prompt_version: ClassVar[str] = "unversioned"

    @abstractmethod
    def build_messages(self, ctx: StageContext) -> list[dict]:
        """Chat messages asking for `GENERATION_CONTRACTS[stage]`."""

    @abstractmethod
    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        """Convert the LLM output to persisted artifacts with derived ids.

        Raise a pydantic `ValidationError` if the content does not fit.
        """

    def present_feedback(self, message: str, ctx: StageContext, produced: Sequence[BaseModel]) -> str:
        """A consistency violation message as the model should read it. The messages come from the
        domain and name real ids; a generator whose prompt showed the model something else (aliases)
        overrides this to say it in the prompt's terms. Default: the message unchanged."""
        return message


class LoopGenerator(StageGenerator):
    """A stage that runs its own loop of LLM calls inside one message (the swot_errc_cycle).

    The stage has several generation contracts; the generator owns the loop and calls the
    runner's services for every LLM call, so each call keeps the runner's retries, text
    validation, feedback and tracing. The runner then runs the consistency checks once on the
    final result: a retry happens per call (see `LoopServices.call_checked`), never as a
    regeneration of the whole row.
    """

    contracts: ClassVar[tuple[type, ...]]

    def build_messages(self, ctx: StageContext) -> list[dict]:
        raise NotImplementedError("a loop generator builds its messages inside run_loop")

    def to_artifacts(self, generated: BaseModel, ctx: StageContext) -> list[tuple[ArtifactType, BaseModel]]:
        raise NotImplementedError("a loop generator converts inside run_loop")

    @abstractmethod
    async def run_loop(self, ctx: StageContext, services: "LoopServices") -> list[tuple[ArtifactType, BaseModel]]:
        """All artifacts of the row, in the order they are returned. Raise `GenerationFailed`
        (or let the underlying error through) to fail the row."""


class RunOutcome(BaseModel):
    artifacts: list[ArtifactRecord] = []
    consistency: ConsistencyReport | None = None
    failure: StageFailure | None = None
    # How many times the row was regenerated because of consistency errors.
    consistency_retries: int = 0

    @property
    def success(self) -> bool:
        return self.failure is None


def _record(row: StageRow, artifact_type: ArtifactType, model: BaseModel) -> ArtifactRecord:
    """The wire record of a persisted artifact. Most models carry their own `id`;
    `Brief` has none, so its record id is derived like any other (index 0)."""
    artifact_id = getattr(model, "id", None) or derive_artifact_id(row.id, artifact_type, 0)
    return ArtifactRecord(id=artifact_id, type=artifact_type, data=model.model_dump(mode="json"))


def _conversion_feedback_message(error: str) -> dict:
    return {
        "role": "user",
        "content": "Your previous answer could not be used, for this reason:\n"
        f"{error[:_MAX_FEEDBACK_ERROR]}\nFix it and answer again.",
    }


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
            if isinstance(generator, LoopGenerator):
                if generator.stage != stage or tuple(generator.contracts) != tuple(contracts):
                    raise ValueError(
                        f"loop generator for {stage.value} must declare that stage and exactly its generation "
                        f"contracts {[c.__name__ for c in contracts]}"
                    )
            elif generator.stage != stage or len(contracts) != 1:
                raise ValueError(
                    f"generator for {stage.value} must declare that stage and the stage must have exactly "
                    f"one generation contract (got {len(contracts)}); a multi-contract stage needs a LoopGenerator"
                )
        self._generators = dict(generators)
        self._llm = llm
        self._judge = judge
        self._rules = rules
        self._checks = checks
        self._retry_wait = retry_wait

    def has_generator(self, stage: Stage) -> bool:
        return stage in self._generators

    def prompt_version(self, stage: Stage) -> str:
        return self._generators[stage].prompt_version

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
                closure=gather_closure(row, rows),
                rows=rows,
            )
        except ContextError as e:
            return self._failed(f"context: {e}")

        if isinstance(generator, LoopGenerator):
            return await self._run_loop(generator, ctx)

        contract = GENERATION_CONTRACTS[row.stage][0]
        feedback: list[str] = []
        retries = 0
        while True:
            try:
                models = await self._generate(generator, ctx, contract, feedback, retries)
            except ContextError as e:
                return self._failed(f"context: {e}")
            except (LLMError, ValueError, DegenerateTextError, GenerationFailed) as e:
                return self._failed(str(e))

            with tracing.span("consistency_rules"):
                violations = run_deterministic(row, [m for _, m in models], rows, self._rules)
            errors = [generator.present_feedback(v.message, ctx, [m for _, m in models]) for v in violations if v.severity == "error"]
            if not errors or retries >= MAX_CONSISTENCY_RETRIES:
                break
            retries += 1
            feedback = errors
            log.info("consistency_retry", row_id=row.id, stage=row.stage.value, retry=retries, errors=len(errors))

        fresh = [m for _, m in models]
        records = [_record(row, t, m) for t, m in models]
        reports, unavailable = await run_judge(
            row, fresh, rows, self._judge, self._checks, artifact_ids=[r.id for r in records]
        )
        return RunOutcome(
            artifacts=records,
            consistency=build_report(violations, reports, unavailable),
            consistency_retries=retries,
        )

    async def _run_loop(self, generator: LoopGenerator, ctx: StageContext) -> RunOutcome:
        row, rows = ctx.row, ctx.rows
        services = LoopServices(self, ctx)
        try:
            models = await generator.run_loop(ctx, services)
            for artifact_type, model in models:
                parse_artifact(_record(row, artifact_type, model))
        except ContextError as e:
            return self._failed(f"context: {e}")
        except (LLMError, ValueError, DegenerateTextError, GenerationFailed) as e:
            return self._failed(str(e))
        with tracing.span("consistency_rules"):
            violations = run_deterministic(row, [m for _, m in models], rows, self._rules)
        records = [_record(row, t, m) for t, m in models]
        reports, unavailable = await run_judge(
            row, [m for _, m in models], rows, self._judge, self._checks, artifact_ids=[r.id for r in records]
        )
        return RunOutcome(
            artifacts=records,
            consistency=build_report(violations, reports, unavailable),
            consistency_retries=services.consistency_retries,
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

        def convert(generated: BaseModel) -> list[tuple[ArtifactType, BaseModel]]:
            models = generator.to_artifacts(generated, ctx)
            if not models:
                raise ValueError(f"generator for {ctx.row.stage.value} produced no artifacts")
            # Validate what be will validate, so a bad artifact is a generation
            # failure here and not a 422 (and a dead-lettered message) there.
            for artifact_type, model in models:
                parse_artifact(_record(ctx.row, artifact_type, model))
            return models

        return await self._call(
            contract=contract,
            messages=messages,
            convert=convert,
            language=ctx.language,
            prompt_version=generator.prompt_version,
            consistency_round=consistency_round,
        )

    async def _call(
        self,
        *,
        contract: type,
        messages: list[dict],
        convert: Callable[[BaseModel], T],
        language: str,
        prompt_version: str,
        consistency_round: int = 0,
        label: str = "",
    ) -> T:
        """One LLM call with everything around it: retries on LLM errors, schema/conversion errors
        and degenerate text, the conversion error shown to the model on the next attempt, the
        one-retry length rule, the text validation and the tracing. `convert` turns the generated
        model into the result and may raise `ValueError` (retried with its message as feedback)."""
        attempts = {"n": 0}
        length_hits = {"n": 0}
        # Why the last answer could not be converted (a pydantic or ValueError from
        # `convert`); the next attempt shows it to the model as feedback.
        conversion_error: list[str] = []

        async def attempt() -> T:
            attempts["n"] += 1
            call_messages = [*messages, _conversion_feedback_message(conversion_error[-1])] if conversion_error else messages
            metadata = {
                "attempt": attempts["n"],
                "consistency_round": consistency_round,
                "prompt_version": prompt_version,
                **({"label": label} if label else {}),
            }
            with tracing.generation_span(
                "llm_call", model=self._llm.model_name, input=call_messages, metadata=metadata
            ) as span:
                try:
                    generated = await self._llm.generate_structured(call_messages, contract)
                except LLMError as e:
                    # The finish reason (and the usage of a cut-off answer) goes on the span.
                    span.update(
                        metadata={**metadata, "finish_reason": self._finish_reason()},
                        usage_details=self._llm.last_usage,
                        status_message=str(e),
                    )
                    if isinstance(e, LLMLengthError):
                        length_hits["n"] += 1
                        if length_hits["n"] > MAX_LENGTH_RETRIES:
                            raise GenerationFailed(
                                f"LLM output was cut off (finish_reason=length) on {length_hits['n']} attempts; "
                                "the generation does not fit the output limit"
                            ) from e
                    raise
                span.update(
                    output=generated.model_dump(mode="json"),
                    usage_details=self._llm.last_usage,
                    metadata={**metadata, "finish_reason": self._finish_reason()},
                )
            # Pydantic cannot see a valid-but-degenerate string (wrong script, padding,
            # repeated runs). A retry-worthy finding retries like a schema error and,
            # when retries run out, fails the row. Every finding goes on the span.
            with tracing.span("validate_text") as text_span:
                findings = validate_block_text(contract, generated.model_dump(mode="json"), language)
                text_span.update(
                    metadata={
                        "violations": [
                            {"field": v.field_path, "kind": v.kind, "detail": v.detail, "retry_worthy": v.retry_worthy}
                            for v in findings
                        ]
                    }
                )
                retry_worthy = [v for v in findings if v.retry_worthy]
                if retry_worthy:
                    raise DegenerateTextError(retry_worthy)
            try:
                return convert(generated)
            except ValueError as e:
                conversion_error[:] = [str(e)]
                raise

        return await retry_async(
            attempt,
            retry_on=(LLMError, ValueError, DegenerateTextError),  # pydantic's ValidationError is a ValueError
            wait_min=self._retry_wait,
            wait_max=self._retry_wait,
        )

    def _finish_reason(self) -> str | None:
        return getattr(self._llm, "last_finish_reason", None)

    @staticmethod
    def _failed(message: str) -> RunOutcome:
        return RunOutcome(
            failure=StageFailure(code=StageErrorCode.GENERATION_FAILED, message=message[:_MAX_FAILURE_MESSAGE])
        )


class LoopServices:
    """What a `LoopGenerator` may use: the runner's LLM call and the per-call consistency retry."""

    def __init__(self, runner: StageRunner, ctx: StageContext) -> None:
        self._runner = runner
        self._ctx = ctx
        self.consistency_retries = 0

    async def call(self, contract: type, messages: list[dict], convert: Callable[[BaseModel], T], *, label: str) -> T:
        return await self._runner._call(
            contract=contract, messages=messages, convert=convert, language=self._ctx.language,
            prompt_version=self._runner._generators[self._ctx.row.stage].prompt_version, label=label,
        )

    async def call_checked(
        self,
        contract: type,
        messages: list[dict],
        convert: Callable[[BaseModel], T],
        *,
        label: str,
        artifacts_of: Callable[[T], Sequence[BaseModel]],
    ) -> T:
        """`call`, then the deterministic rules over `artifacts_of(result)` (the artifacts the row would
        hold with this result added). An error violation regenerates THIS call with the violation
        messages as feedback, at most `MAX_CONSISTENCY_RETRIES` times; what is left after that is
        reported by the final consistency pass of the row."""
        ctx, runner = self._ctx, self._runner
        feedback: list[str] = []
        for retry in range(MAX_CONSISTENCY_RETRIES + 1):
            asked = [*messages, _feedback_message(feedback)] if feedback else messages
            result = await runner._call(
                contract=contract, messages=asked, convert=convert, language=ctx.language,
                prompt_version=runner._generators[ctx.row.stage].prompt_version, consistency_round=retry, label=label,
            )
            with tracing.span("consistency_rules"):
                violations = run_deterministic(ctx.row, artifacts_of(result), ctx.rows, runner._rules)
            generator = runner._generators[ctx.row.stage]
            produced = artifacts_of(result)
            errors = [generator.present_feedback(v.message, ctx, produced) for v in violations if v.severity == "error"]
            if not errors or retry >= MAX_CONSISTENCY_RETRIES:
                return result
            feedback = errors
            self.consistency_retries += 1
            log.info("consistency_retry", row_id=ctx.row.id, stage=ctx.row.stage.value, call=label, retry=retry + 1, errors=len(errors))
        raise AssertionError("unreachable")
