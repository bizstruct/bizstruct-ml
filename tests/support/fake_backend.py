"""In-memory stand-in for bizstruct-be, for tests that walk the graph.

Serves the snapshot of a row's closure (`GET …?row=`), applies a posted
`StageResult` the way be would (attempt check, schema check, status transitions,
consistency decision) and creates rows as the graph unfolds: after `brief`, one
`empathy_map` row per segment candidate; after each empathy map, a
`customer_scenario` and an `ideation` row. It talks HTTP through an httpx
`MockTransport`, so the real `BackendClient` is exercised unchanged.

Slice 1 only knows these four stages; later slices extend `expand`.
"""

import json
from itertools import count

import httpx
from bizstruct_domain.schemas import (
    ARTIFACT_MODELS,
    ArtifactType,
    Brief,
    ProjectSnapshot,
    QueueMessage,
    RowTarget,
    Stage,
    StageErrorCode,
    StageResult,
    StageRow,
    StageStatus,
    parse_artifact,
    ready_rows,
)
from pydantic import ValidationError

from bizstruct_ml.adapters.backend_client import BackendClient
from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.strategies.pipeline import Action, Disposition, handle_message

PROJECT_ID = "project_001"


class FakeBackend:
    def __init__(self, idea: str = "Farm produce delivery", language: str = "en", enabled_optional: list[Stage] | None = None) -> None:
        self.idea = idea
        self.language = language
        self.enabled_optional = enabled_optional or []
        self.rows: dict[str, StageRow] = {}
        self.posted: list[StageResult] = []
        self._attempts = count(1)
        self._outbox: dict[str, QueueMessage] = {}
        self.add_row(Stage.BRIEF, 0, {})

    # -- be's own bookkeeping ------------------------------------------------

    def add_row(self, stage: Stage, instance_index: int, refs: dict[Stage, list[str]]) -> StageRow:
        row = StageRow(id=f"row_{stage.value}_{instance_index}", stage=stage, instance_index=instance_index,
                       status=StageStatus.PENDING, refs=refs)
        self.rows[row.id] = row
        return row

    def rows_of(self, stage: Stage) -> list[StageRow]:
        return sorted((r for r in self.rows.values() if r.stage == stage), key=lambda r: r.instance_index)

    def expand(self) -> None:
        """Create the rows whose parents are DONE; idempotent."""
        (brief_row,) = self.rows_of(Stage.BRIEF)
        if brief_row.status == StageStatus.DONE and not self.rows_of(Stage.EMPATHY_MAP):
            brief = parse_artifact(brief_row.artifacts[0])
            assert isinstance(brief, Brief)
            for k, _ in enumerate(brief.customer_segment_candidates):
                self.add_row(Stage.EMPATHY_MAP, k, {Stage.BRIEF: [brief_row.id]})
        for empathy in self.rows_of(Stage.EMPATHY_MAP):
            if empathy.status != StageStatus.DONE:
                continue
            for stage in (Stage.CUSTOMER_SCENARIO, Stage.IDEATION):
                if not any(r.refs.get(Stage.EMPATHY_MAP) == [empathy.id] for r in self.rows_of(stage)):
                    self.add_row(stage, empathy.instance_index, {Stage.EMPATHY_MAP: [empathy.id]})

    def dispatch_ready(self) -> list[QueueMessage]:
        """Mark every ready row RUNNING with a fresh attempt and return its message."""
        messages = []
        for row_id in ready_rows(list(self.rows.values()), self.enabled_optional):
            row = self.rows[row_id]
            row.status = StageStatus.RUNNING
            row.attempt_id = f"attempt_{next(self._attempts)}"
            message = QueueMessage(
                project_id=PROJECT_ID,
                language=self.language,
                targets=[RowTarget(stage_row_id=row.id, stage=row.stage, attempt_id=row.attempt_id)],
            )
            self._outbox[row.id] = message
            messages.append(message)
        return messages

    def message_for(self, row_id: str) -> QueueMessage:
        """The queue message of a row, dispatching it first if be has not yet."""
        self.dispatch_ready()
        return self._outbox.pop(row_id)

    def closure_of(self, row_id: str) -> list[StageRow]:
        seen: dict[str, StageRow] = {}
        stack = [row_id]
        while stack:
            current = self.rows[stack.pop()]
            if current.id in seen:
                continue
            seen[current.id] = current
            stack.extend(i for ids in current.refs.values() for i in ids)
        return list(seen.values())

    # -- HTTP surface ---------------------------------------------------------

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            row_id = request.url.params["row"]
            if row_id not in self.rows:
                return httpx.Response(404)
            snapshot = ProjectSnapshot(
                project_id=PROJECT_ID, idea=self.idea, language=self.language,
                enabled_optional=self.enabled_optional, rows=self.closure_of(row_id),
            )
            return httpx.Response(200, content=snapshot.model_dump_json())
        return self._apply(StageResult.model_validate(json.loads(request.content)))

    def _apply(self, result: StageResult) -> httpx.Response:
        self.posted.append(result)
        row = self.rows.get(result.stage_row_id)
        if row is None:
            return httpx.Response(404)
        if result.attempt_id == row.attempt_id and row.status == StageStatus.DONE:
            return httpx.Response(200)  # duplicate
        if result.attempt_id != row.attempt_id or row.status != StageStatus.RUNNING:
            return httpx.Response(409)
        if result.status == "failed":
            assert result.error is not None
            row.status, row.error_code, row.error = StageStatus.ERROR, result.error.code, result.error.message
            return httpx.Response(200)
        try:
            for record in result.artifacts:
                ARTIFACT_MODELS[ArtifactType(record.type)].model_validate(record.data)
        except ValidationError as e:
            row.status, row.error_code, row.error = StageStatus.ERROR, StageErrorCode.GENERATION_FAILED, str(e)
            return httpx.Response(422, text=str(e))
        row.artifacts = list(result.artifacts)
        row.consistency = result.consistency
        has_errors = result.consistency is not None and result.consistency.has_errors
        row.status = StageStatus.AWAITING_DECISION if has_errors else StageStatus.DONE
        self.expand()
        return httpx.Response(200)

    # -- driver ---------------------------------------------------------------

    def client(self) -> BackendClient:
        http = httpx.AsyncClient(base_url="http://be.test", transport=httpx.MockTransport(self.handler))
        return BackendClient(client=http, retry_wait_min=0, retry_wait_max=0)

    async def run_to_completion(self, runner: StageRunner, *, max_rounds: int = 20) -> list[Disposition]:
        """Dispatch ready rows and hand each message to the pipeline until nothing is ready."""
        client = self.client()
        dispositions: list[Disposition] = []
        for _ in range(max_rounds):
            messages = self.dispatch_ready()
            if not messages:
                return dispositions
            for message in messages:
                dispositions.append(await handle_message(message, client, runner))
        raise AssertionError("graph did not settle")


def all_done(backend: FakeBackend) -> bool:
    return all(r.status == StageStatus.DONE for r in backend.rows.values())


__all__ = ["FakeBackend", "all_done", "Action"]
