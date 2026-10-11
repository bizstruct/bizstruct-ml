"""Pipeline strategy: dispositions for every path (ADR-0011 Q4, Q5, Q9)."""
import json

import httpx
import pytest
from bizstruct_domain.schemas import (
    QueueMessage,
    RowTarget,
    Stage,
    StageErrorCode,
    StageResult,
    StageStatus,
)

from bizstruct_ml.adapters.backend_client import BackendClient
from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.client import LLMError
from bizstruct_ml.strategies.pipeline import Action, build_runner, handle_message
from tests.support.fakes import EmpathyMapTestGenerator, FakeLLM, brief_row, empathy_generated, empathy_row, snapshot_for


class Backend:
    """A mock transport that serves a snapshot and records posted results."""

    def __init__(self, snapshot=None, get_status: int = 200, post_status: int = 200) -> None:
        self.snapshot = snapshot
        self.get_status = get_status
        self.post_status = post_status
        self.gets: list[httpx.Request] = []
        self.results: list[StageResult] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            self.gets.append(request)
            if self.get_status != 200:
                return httpx.Response(self.get_status, text="err")
            return httpx.Response(200, content=self.snapshot.model_dump_json())
        self.results.append(StageResult.model_validate(json.loads(request.content)))
        return httpx.Response(self.post_status, text="err")

    def client(self) -> BackendClient:
        http = httpx.AsyncClient(base_url="http://be.test", transport=httpx.MockTransport(self.handler))
        return BackendClient(client=http, retry_wait_min=0, retry_wait_max=0)


def message(*, attempt_id: str = "att1", stage: Stage = Stage.EMPATHY_MAP, targets: int = 1) -> QueueMessage:
    target = RowTarget(stage_row_id="row_em_0", stage=stage, attempt_id=attempt_id)
    return QueueMessage(project_id="project_001", language="en", targets=[target] * targets)


def runner(llm: FakeLLM | None = None) -> StageRunner:
    return StageRunner(
        {Stage.EMPATHY_MAP: EmpathyMapTestGenerator()},
        llm or FakeLLM([empathy_generated()]),
        ConsistencyJudge(FakeJudgeModel(), retry_wait=0),
        retry_wait=0,
    )


def default_backend(**row_overrides) -> Backend:
    row = empathy_row(**row_overrides)
    return Backend(snapshot_for(row, brief_row()))


async def test_success_posts_a_success_result_and_completes():
    backend = default_backend()
    disposition = await handle_message(message(), backend.client(), runner())
    assert disposition.action == Action.COMPLETE and disposition.reason == "ResultApplied"
    (result,) = backend.results
    assert result.status == "success" and result.attempt_id == "att1" and result.stage_row_id == "row_em_0"
    assert result.artifacts[0].type == "empathy_map" and result.consistency is not None
    assert backend.gets[0].url.params["row"] == "row_em_0"


async def test_generation_failure_posts_a_failed_result_with_generation_failed():
    backend = default_backend()
    disposition = await handle_message(message(), backend.client(), runner(FakeLLM([LLMError("boom")])))
    assert disposition.action == Action.COMPLETE
    (result,) = backend.results
    assert result.status == "failed" and result.artifacts == []
    assert result.error is not None and result.error.code == StageErrorCode.GENERATION_FAILED
    assert "boom" in result.error.message


async def test_an_unexpected_exception_in_the_runner_still_posts_a_failed_result():
    class Boom(StageRunner):
        async def run(self, *args, **kwargs):
            raise RuntimeError("bug")

    boom = Boom({Stage.EMPATHY_MAP: EmpathyMapTestGenerator()}, FakeLLM([]), ConsistencyJudge(FakeJudgeModel()))
    backend = default_backend()
    disposition = await handle_message(message(), backend.client(), boom)
    assert disposition.action == Action.COMPLETE
    assert backend.results[0].status == "failed" and "bug" in backend.results[0].error.message


async def test_more_than_one_target_is_dead_lettered_without_any_http():
    backend = default_backend()
    disposition = await handle_message(message(targets=2), backend.client(), runner())
    assert disposition.action == Action.DEAD_LETTER
    assert "agent phase" in disposition.description
    assert backend.gets == [] and backend.results == []


async def test_a_stage_without_a_generator_is_dead_lettered_with_a_reason():
    backend = default_backend()
    disposition = await handle_message(message(stage=Stage.ENVIRONMENT_SCAN), backend.client(), runner())
    assert disposition.action == Action.DEAD_LETTER and disposition.reason == "NoGenerator"
    assert "environment_scan" in disposition.description
    assert backend.gets == []


async def test_a_stale_attempt_completes_without_work():
    backend = default_backend(attempt_id="att2")
    llm = FakeLLM([empathy_generated()])
    disposition = await handle_message(message(attempt_id="att1"), backend.client(), runner(llm))
    assert disposition.action == Action.COMPLETE and disposition.reason == "StaleAttempt"
    assert llm.calls == [] and backend.results == []


async def test_a_done_row_with_the_same_attempt_completes_without_work():
    backend = default_backend(status=StageStatus.DONE)
    llm = FakeLLM([empathy_generated()])
    disposition = await handle_message(message(), backend.client(), runner(llm))
    assert disposition.action == Action.COMPLETE and disposition.reason == "AlreadyApplied"
    assert llm.calls == [] and backend.results == []


@pytest.mark.parametrize(
    "status",
    [StageStatus.AWAITING_DECISION, StageStatus.ERROR, StageStatus.PENDING, StageStatus.CONSISTENCY_CHECK],
)
async def test_a_row_that_is_not_running_completes_without_work_even_with_the_same_attempt(status):
    backend = default_backend(status=status)
    llm = FakeLLM([empathy_generated()])
    disposition = await handle_message(message(), backend.client(), runner(llm))
    assert disposition.action == Action.COMPLETE and disposition.reason == "NotRunning"
    assert llm.calls == [] and backend.results == []


async def test_a_done_row_with_a_different_attempt_is_stale_not_applied():
    backend = default_backend(status=StageStatus.DONE, attempt_id="att2")
    disposition = await handle_message(message(attempt_id="att1"), backend.client(), runner())
    assert disposition.reason == "StaleAttempt"


async def test_a_row_missing_from_the_snapshot_is_dead_lettered():
    backend = Backend(snapshot_for(empathy_row("row_other"), brief_row()))
    disposition = await handle_message(message(), backend.client(), runner())
    assert disposition.action == Action.DEAD_LETTER and disposition.reason == "RowNotFound"


async def test_a_stage_mismatch_between_message_and_row_is_dead_lettered():
    row = empathy_row().model_copy(update={"stage": Stage.BRIEF})
    backend = Backend(snapshot_for(row))
    disposition = await handle_message(message(), backend.client(), runner())
    assert disposition.reason == "StageMismatch"


@pytest.mark.parametrize(
    ("get_status", "action", "reason"),
    [
        (404, Action.DEAD_LETTER, "ProjectNotFound"),
        (403, Action.DEAD_LETTER, "SnapshotRejected_403"),
        (500, Action.ABANDON, "BackendUnavailable"),
    ],
)
async def test_snapshot_response_codes(get_status, action, reason):
    backend = Backend(get_status=get_status)
    disposition = await handle_message(message(), backend.client(), runner())
    assert (disposition.action, disposition.reason) == (action, reason)


@pytest.mark.parametrize(
    ("post_status", "action", "reason"),
    [
        (200, Action.COMPLETE, "ResultApplied"),
        (409, Action.COMPLETE, "ResultStale"),
        (404, Action.DEAD_LETTER, "HookRejected_404"),
        (422, Action.DEAD_LETTER, "HookRejected_422"),
        (500, Action.ABANDON, "HookUnavailable"),
    ],
)
async def test_hook_response_codes(post_status, action, reason):
    backend = default_backend()
    backend.post_status = post_status
    disposition = await handle_message(message(), backend.client(), runner())
    assert (disposition.action, disposition.reason) == (action, reason)


def test_the_worker_starts_and_rejects_stages_that_have_no_generator_yet():
    from tests.test_judge_factory import make_settings

    runner_ = build_runner(make_settings(judge_provider="fake"))
    assert runner_.has_generator(Stage.BRIEF) and runner_.has_generator(Stage.IDEATION)
    assert runner_.has_generator(Stage.PATTERNS) and runner_.has_generator(Stage.CANVAS)
    assert all(runner_.has_generator(s) for s in (Stage.SWOT_ERRC_CYCLE, Stage.STORYTELLING, Stage.FUTURE_SCENARIO, Stage.PITCH)) and not runner_.has_generator(Stage.ENVIRONMENT_SCAN)
