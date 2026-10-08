"""Turn a snapshot closure into the artifacts a generator or a check needs.

Pure functions over `StageRow`s: no queues, no HTTP. Artifacts come out as the
persisted domain models (via `parse_artifact`), never as raw dicts.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from bizstruct_domain.schemas import (
    ARTIFACT_HOLDERS,
    ARTIFACT_MODELS,
    Arity,
    ArtifactType,
    InputBindingError,
    RuleInput,
    Stage,
    StageRow,
    StageStatus,
    bind_inputs,
    parse_artifact,
)
from pydantic import BaseModel


class ContextError(Exception):
    """The closure does not hold what was asked for, or holds it ambiguously."""


def rows_by_id(rows: Sequence[StageRow]) -> dict[str, StageRow]:
    return {row.id: row for row in rows}


def parse_row_artifacts(row: StageRow) -> list[BaseModel]:
    """The persisted models of the artifacts a row holds, in stored order."""
    return [parse_artifact(record) for record in row.artifacts]


def gather_context(row: StageRow, rows: Mapping[str, StageRow]) -> dict[Stage, list[BaseModel]]:
    """Artifacts of the rows listed in `row.refs`, labelled by stage.

    Raises `ContextError` if a referenced row is missing from `rows` or belongs
    to a different stage than the ref key says.
    """
    context: dict[Stage, list[BaseModel]] = {}
    for stage, ids in row.refs.items():
        artifacts: list[BaseModel] = []
        for row_id in ids:
            ref = rows.get(row_id)
            if ref is None:
                raise ContextError(f"row {row.id} refs {stage.value} row {row_id}, which is not in the snapshot")
            if ref.stage != stage:
                raise ContextError(f"row {row.id} refs {row_id} as {stage.value}, but it is a {ref.stage.value} row")
            artifacts.extend(parse_row_artifacts(ref))
        context[stage] = artifacts
    return context


def gather_closure(row: StageRow, rows: Mapping[str, StageRow]) -> dict[Stage, list[BaseModel]]:
    """Artifacts of every row reachable from `row` through `refs`, transitively
    (the row itself excluded), labelled by stage. Same errors as `gather_context`."""
    closure: dict[Stage, list[BaseModel]] = {}
    seen = {row.id}
    frontier = [row]
    while frontier:
        direct = [(stage, ids) for current in frontier for stage, ids in current.refs.items()]
        frontier = []
        for stage, ids in direct:
            for row_id in ids:
                if row_id in seen:
                    continue
                seen.add(row_id)
                ref = rows.get(row_id)
                if ref is None:
                    raise ContextError(f"row {row.id} reaches {stage.value} row {row_id}, which is not in the snapshot")
                closure.setdefault(ref.stage, []).extend(parse_row_artifacts(ref))
                frontier.append(ref)
    return closure


def _of_type(artifacts: Sequence[BaseModel], artifact: ArtifactType) -> list[BaseModel]:
    model = ARTIFACT_MODELS[artifact]
    return [a for a in artifacts if isinstance(a, model)]


def gather_inputs(
    inputs: Sequence[RuleInput],
    *,
    fresh_row: StageRow,
    fresh_artifacts: Sequence[BaseModel],
    rows: Mapping[str, StageRow],
) -> list[tuple[Any, ...]]:
    """Argument tuples for a `ConsistencyRule`/`JudgeCheck` (ADR-0012): one tuple, or one per
    instance of the `EACH` input. The kinds are applied by the domain's `bind_inputs`; this
    function gathers its CANDIDATES per artifact type.

    `fresh_artifacts` stand in for whatever `fresh_row` held before: the row was just
    (re)generated, so its stored artifacts are stale and never read from `rows`.

    - `MANY`, `EACH`, `FINAL`: the fresh artifacts of the type plus, for each stage that can hold
      the type (`ARTIFACT_HOLDERS`, a Canvas lives in `canvas` and `swot_errc_cycle`): the
      instances of the rows `refs` names under that stage (every one must exist, be DONE and
      hold artifacts, else `ContextError`; the group is defined by the row's refs), otherwise
      those of the DONE rows of that stage in the closure. `FINAL` also needs the Swots of the
      cycle, gathered the same way.
    - `ONE`: the fresh artifacts of the type plus those of the rows the fresh row's `refs` name
      (any key). If that yields NO candidate, the same holder rule as above applies (a row whose
      refs name no holder stage of the type falls back to the closure; one that names a holder
      stage must have usable rows or it is a `ContextError`). Several candidates stay an error.

    Raises `ContextError` when a required input is missing or a `ONE` is ambiguous.
    """
    done = [r for r in rows.values() if r.status == StageStatus.DONE and r.id != fresh_row.id]
    direct = [rows[i] for ids in fresh_row.refs.values() for i in ids if i in rows and i != fresh_row.id]
    candidates: dict[ArtifactType, list[BaseModel]] = {}
    for spec in inputs:
        wanted = [spec.artifact, ArtifactType.SWOT] if spec.arity is Arity.FINAL else [spec.artifact]
        for artifact in wanted:
            if artifact in candidates:
                continue
            pool = _of_type(fresh_artifacts, artifact)
            if spec.arity is Arity.ONE:
                for ref in direct:
                    pool.extend(_of_type(parse_row_artifacts(ref), artifact))
            if spec.arity is not Arity.ONE or not pool:
                # MANY, EACH, FINAL always; ONE only when its own pool found nothing (ADR-0001)
                for holder in ARTIFACT_HOLDERS[artifact]:
                    if fresh_row.refs.get(holder):
                        # the row names this holder stage: its rows must be usable, else ContextError
                        pool.extend(_of_type(_direct_artifacts(fresh_row, holder, rows), artifact))
                    else:
                        for other in done:
                            if other.stage == holder:
                                pool.extend(_of_type(parse_row_artifacts(other), artifact))
            candidates[artifact] = pool
    try:
        return bind_inputs(inputs, candidates)
    except InputBindingError as e:
        raise ContextError(f"row {fresh_row.id}: {e}") from e


def _direct_artifacts(fresh_row: StageRow, stage: Stage, rows: Mapping[str, StageRow]) -> list[BaseModel]:
    """Artifacts of the rows `fresh_row.refs` lists under `stage`; each must be a DONE row with artifacts."""
    artifacts: list[BaseModel] = []
    for row_id in fresh_row.refs[stage]:
        ref = rows.get(row_id)
        if ref is None:
            raise ContextError(f"row {fresh_row.id} refs {stage.value} row {row_id}, which is not in the snapshot")
        if ref.status != StageStatus.DONE:
            raise ContextError(f"row {fresh_row.id} refs {stage.value} row {row_id}, which is {ref.status.value}, not done")
        if not ref.artifacts:
            raise ContextError(f"row {fresh_row.id} refs {stage.value} row {row_id}, which has no artifacts")
        artifacts.extend(parse_row_artifacts(ref))
    return artifacts
