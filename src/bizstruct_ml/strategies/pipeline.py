"""Pipeline strategy: one queue message, one stage row (ADR-0011 Q4, Q5, Q9).

`handle_message` decides what happens to the message and returns a
`Disposition`; settling the message on the queue is the consumer's job. ml never
writes row statuses: it posts a `StageResult` and be applies the transitions.
"""

import time
from enum import StrEnum

import bizstruct_domain
import structlog
from bizstruct_domain.schemas import (
    ProjectSnapshot,
    QueueMessage,
    Stage,
    StageErrorCode,
    StageFailure,
    StageResult,
    StageRow,
    StageStatus,
)
from pydantic import BaseModel

from bizstruct_ml.adapters.backend_client import (
    BackendClient,
    BackendRejectedError,
    BackendUnavailableError,
    HookFailedError,
    HookRejectedError,
    HookStaleError,
    ProjectNotFoundError,
)
from bizstruct_ml.config import Settings
from bizstruct_ml.core.stage_runner import RunOutcome, StageGenerator, StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.factory import build_judge_model
from bizstruct_ml.judge.guard import assert_different_family
from bizstruct_ml.llm.client import GENERATOR_FAMILY, LLMClient
from bizstruct_ml.observability import tracing
from bizstruct_ml.stages import SLICE_1_GENERATORS

log = structlog.get_logger()

# Stage generators the pipeline can run. A stage absent here is dead-lettered
# with a clear reason; slices add their stages by registering them here.
STAGE_GENERATORS: dict[Stage, StageGenerator] = {**SLICE_1_GENERATORS}


class Action(StrEnum):
    COMPLETE = "complete"
    DEAD_LETTER = "dead_letter"
    ABANDON = "abandon"


class Disposition(BaseModel):
    action: Action
    reason: str = ""
    description: str = ""


def _complete(reason: str) -> Disposition:
    return Disposition(action=Action.COMPLETE, reason=reason)


def _dead_letter(reason: str, description: str) -> Disposition:
    return Disposition(action=Action.DEAD_LETTER, reason=reason, description=description)


def _abandon(reason: str, description: str = "") -> Disposition:
    return Disposition(action=Action.ABANDON, reason=reason, description=description)


def build_runner(settings: Settings) -> StageRunner:
    """Build the runner from settings; raise at startup on a bad configuration.

    Raises `FamilyGuardError` if the judge is from the generator's family and
    `JudgeConfigError`/`RuntimeError` if either model is misconfigured.
    """
    judge_model = build_judge_model(settings)
    assert_different_family(GENERATOR_FAMILY, judge_model.family)
    return StageRunner(STAGE_GENERATORS, LLMClient(), ConsistencyJudge(judge_model))


async def handle_message(
    message: QueueMessage,
    backend: BackendClient,
    runner: StageRunner,
    *,
    delivery_count: int = 1,
) -> Disposition:
    if len(message.targets) != 1:
        return _dead_letter(
            "MultiTargetNotSupported",
            f"{len(message.targets)} targets: multi-target is reserved for the agent phase",
        )
    target = message.targets[0]
    bound_log = log.bind(project_id=message.project_id, row_id=target.stage_row_id, stage=target.stage.value)

    if not runner.has_generator(target.stage):
        bound_log.error("message_dead_lettered", reason="no_generator")
        return _dead_letter("NoGenerator", f"No generator is registered for stage '{target.stage.value}'")

    loaded = await _load(message, backend, bound_log)
    if isinstance(loaded, Disposition):
        return loaded
    snapshot, row = loaded

    # The snapshot's language is the authoritative one (the message carries a copy
    # only for early attribution); the runner and the trace metadata both use it.
    with tracing.trace_block_generation(
        project_id=message.project_id,
        block=target.stage.value,
        mode="pipeline",
        attempt_number=delivery_count,
        domain_version=bizstruct_domain.__version__,
        language=snapshot.language,
        prompt_version=runner.prompt_version(target.stage),
    ) as root_span:
        try:
            disposition = await _generate_and_send(message, snapshot, row, backend, runner, bound_log)
        finally:
            await tracing.aflush()
        root_span.update(output={"outcome": disposition.action.value, "reason": disposition.reason})
        return disposition


async def _load(message: QueueMessage, backend: BackendClient, bound_log) -> tuple[ProjectSnapshot, StageRow] | Disposition:
    """Fetch the snapshot and decide whether there is any work: a Disposition means
    the message is settled without generating (missing, stale or already applied)."""
    target = message.targets[0]
    try:
        snapshot = await backend.get_snapshot(message.project_id, target.stage_row_id)
    except ProjectNotFoundError as e:
        bound_log.error("message_dead_lettered", reason="project_not_found")
        return _dead_letter("ProjectNotFound", str(e))
    except BackendRejectedError as e:
        bound_log.error("message_dead_lettered", reason="snapshot_rejected", status_code=e.status_code)
        return _dead_letter(f"SnapshotRejected_{e.status_code}", f"HTTP {e.status_code}: {e.body}")
    except BackendUnavailableError as e:
        bound_log.warning("message_abandoned", reason="backend_unavailable", error=str(e))
        return _abandon("BackendUnavailable", str(e))

    row = next((r for r in snapshot.rows if r.id == target.stage_row_id), None)
    if row is None:
        bound_log.error("message_dead_lettered", reason="row_not_in_snapshot")
        return _dead_letter("RowNotFound", f"Row {target.stage_row_id} is not in the snapshot")
    if row.stage != target.stage:
        return _dead_letter("StageMismatch", f"Message says {target.stage.value}, row is {row.stage.value}")

    if target.attempt_id != row.attempt_id:
        bound_log.info("stale_attempt", message_attempt=target.attempt_id, row_attempt=row.attempt_id)
        return _complete("StaleAttempt")
    if row.status == StageStatus.DONE:
        bound_log.info("already_applied")
        return _complete("AlreadyApplied")
    return snapshot, row


async def _generate_and_send(
    message: QueueMessage,
    snapshot: ProjectSnapshot,
    row: StageRow,
    backend: BackendClient,
    runner: StageRunner,
    bound_log,
) -> Disposition:
    target = message.targets[0]
    bound_log.info("generation_started")
    start = time.monotonic()
    try:
        outcome = await runner.run(row, snapshot, snapshot.language)
    except Exception as e:  # a bug or an unexpected provider error must not loop the message forever
        bound_log.error("generation_crashed", error=str(e), exc_info=True)
        outcome = RunOutcome(
            failure=StageFailure(
                code=StageErrorCode.GENERATION_FAILED, message=f"{type(e).__name__}: {e}"[:2000]
            )
        )
    bound_log.info(
        "generation_finished",
        success=outcome.success,
        duration_s=round(time.monotonic() - start, 2),
        consistency_retries=outcome.consistency_retries,
    )

    result = StageResult(
        project_id=message.project_id,
        stage_row_id=row.id,
        attempt_id=target.attempt_id,
        status="success" if outcome.success else "failed",
        artifacts=outcome.artifacts,
        error=outcome.failure,
        consistency=outcome.consistency,
    )
    with tracing.span("send_result") as span:
        try:
            await backend.send_result(result)
        except HookStaleError as e:
            span.update(output={"outcome": "complete", "reason": "stale"})
            bound_log.info("result_stale", error=str(e))
            return _complete("ResultStale")
        except HookRejectedError as e:
            span.update(output={"status_code": e.status_code, "outcome": "dead_letter"})
            bound_log.error("result_rejected", status_code=e.status_code, body=e.body)
            return _dead_letter(f"HookRejected_{e.status_code}", f"HTTP {e.status_code}: {e.body}")
        except HookFailedError as e:
            span.update(output={"outcome": "abandon", "error": str(e)})
            bound_log.warning("result_failed", error=str(e))
            return _abandon("HookUnavailable", str(e))
    bound_log.info("message_completed")
    return _complete("ResultApplied")
