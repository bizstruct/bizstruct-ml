"""In-memory stand-in for bizstruct-be, for tests that walk the graph.

Serves the snapshot of a row's closure (`GET …?row=`), applies a posted
`StageResult` the way be would (attempt check, schema check, status transitions,
consistency decision) and creates rows as the graph unfolds, per ADR-0011:
after `brief`, one `empathy_map` row per segment candidate; after each empathy
map, a `customer_scenario` and an `ideation` row (instance_index 0: the segment
is found through refs); once every scenario and ideation row exists, one
`patterns` row (refs: all of them); once Patterns is DONE, one `canvas` row per
group from the domain's `canvas_rows_for` (instance_index = position of the
group in `Patterns.groups`). It talks HTTP through an httpx `MockTransport`, so
the real `BackendClient` is exercised unchanged.

After each DONE canvas row, one `swot_errc_cycle` row (refs: that canvas row; the
environment_scan row would be added only if the project enabled it, and no generator
exists for it yet).

`through` is the last stage the fake creates rows for: slice 1 tests keep the
default (`ideation`), slice 2 passes `Stage.CANVAS`, slice 3 `Stage.SWOT_ERRC_CYCLE`.
"""

import json
from itertools import count

import httpx
from bizstruct_domain.schemas import (
    ARTIFACT_MODELS,
    ArtifactType,
    Brief,
    Patterns,
    ProjectSnapshot,
    QueueMessage,
    RowTarget,
    Stage,
    StageErrorCode,
    StageResult,
    StageRow,
    StageStatus,
    parse_artifact,
    canvas_rows_for,
    ready_rows,
    row_of_artifact,
)
from pydantic import ValidationError

from bizstruct_ml.adapters.backend_client import BackendClient
from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.strategies.pipeline import Action, Disposition, handle_message

PROJECT_ID = "project_001"


class FakeBackend:
    def __init__(
        self,
        idea: str = "Farm produce delivery",
        language: str = "en",
        enabled_optional: list[Stage] | None = None,
        through: Stage = Stage.IDEATION,
    ) -> None:
        self.idea = idea
        self.through = through
        self.language = language
        self.enabled_optional = enabled_optional or []
        self.rows: dict[str, StageRow] = {}
        self.posted: list[StageResult] = []
        self._attempts = count(1)
        self._outbox: dict[str, QueueMessage] = {}
        self.add_row(Stage.BRIEF, 0, {})

    # -- be's own bookkeeping ------------------------------------------------

    def add_row(self, stage: Stage, instance_index: int, refs: dict[Stage, list[str]], suffix: int | None = None) -> StageRow:
        """`suffix` only names the row (default: the instance_index); customer_scenario and ideation
        rows are named after their segment but all have instance_index 0 (ADR-0011)."""
        name = instance_index if suffix is None else suffix
        row = StageRow(id=f"row_{stage.value}_{name}", stage=stage, instance_index=instance_index,
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
                    self.add_row(stage, 0, {Stage.EMPATHY_MAP: [empathy.id]}, suffix=empathy.instance_index)
        if self.through == Stage.IDEATION:
            return
        empathies = self.rows_of(Stage.EMPATHY_MAP)
        scenarios, ideations = self.rows_of(Stage.CUSTOMER_SCENARIO), self.rows_of(Stage.IDEATION)
        if (
            empathies
            and len(scenarios) == len(ideations) == len(empathies)
            and not self.rows_of(Stage.PATTERNS)
        ):
            self.add_row(Stage.PATTERNS, 0, {
                Stage.CUSTOMER_SCENARIO: [r.id for r in scenarios],
                Stage.IDEATION: [r.id for r in ideations],
            })
        (patterns_row,) = self.rows_of(Stage.PATTERNS) or [None]
        if self.through == Stage.PATTERNS or patterns_row is None or patterns_row.status != StageStatus.DONE:
            return
        if not self.rows_of(Stage.CANVAS):
            patterns = parse_artifact(patterns_row.artifacts[0])
            assert isinstance(patterns, Patterns)
            for i, spec in enumerate(canvas_rows_for(patterns)):
                group_maps = []
                for empathy_map_id in spec.empathy_map_ids:
                    found = row_of_artifact(empathies, empathy_map_id)
                    assert found is not None, f"no empathy_map row holds {empathy_map_id}"
                    group_maps.append(found)
                ids = {r.id for r in group_maps}
                self.add_row(Stage.CANVAS, i, {
                    Stage.BRIEF: [self.rows_of(Stage.BRIEF)[0].id],
                    Stage.EMPATHY_MAP: [r.id for r in group_maps],
                    Stage.CUSTOMER_SCENARIO: [r.id for r in scenarios if r.refs[Stage.EMPATHY_MAP][0] in ids],
                    Stage.IDEATION: [r.id for r in ideations if r.refs[Stage.EMPATHY_MAP][0] in ids],
                    Stage.PATTERNS: [patterns_row.id],
                })

        if self.through == Stage.CANVAS:
            return
        for canvas_row in self.rows_of(Stage.CANVAS):
            if canvas_row.status == StageStatus.DONE and not any(
                r.refs.get(Stage.CANVAS) == [canvas_row.id] for r in self.rows_of(Stage.SWOT_ERRC_CYCLE)
            ):
                self.add_row(Stage.SWOT_ERRC_CYCLE, 0, {Stage.CANVAS: [canvas_row.id]}, suffix=canvas_row.instance_index)

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
