"""Turn a snapshot closure into the artifacts a generator or a check needs.

Pure functions over `StageRow`s: no queues, no HTTP. Artifacts come out as the
persisted domain models (via `parse_artifact`), never as raw dicts.
"""

import inspect
import types
import typing
from collections.abc import Mapping, Sequence
from typing import Any

from bizstruct_domain.schemas import (
    ARTIFACT_MODELS,
    ARTIFACT_STAGE,
    ConsistencyRule,
    RuleInput,
    Stage,
    StageArity,
    StageRow,
    StageStatus,
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


def _of_stage(artifacts: Sequence[BaseModel], stage: Stage) -> list[BaseModel]:
    return [a for a in artifacts if _stage_of(a) == stage]


_STAGE_OF_MODEL: dict[type, Stage] = {model: ARTIFACT_STAGE[t] for t, model in ARTIFACT_MODELS.items()}


def _stage_of(artifact: BaseModel) -> Stage | None:
    return _STAGE_OF_MODEL.get(type(artifact))


def gather_inputs(
    inputs: Sequence[RuleInput],
    *,
    fresh_row: StageRow,
    fresh_artifacts: Sequence[BaseModel],
    rows: Mapping[str, StageRow],
    expected_types: Sequence[tuple[type, ...] | None] | None = None,
) -> list[Any]:
    """Gather the arguments of a `ConsistencyRule`/`JudgeCheck`, in `inputs` order.

    `fresh_artifacts` stand in for whatever `fresh_row` held before: the row
    was just (re)generated, so its stored artifacts are stale.

    - ONE: the single artifact of that stage reachable from the fresh row or
      its direct refs. Zero or several is a `ContextError` (several is the
      ambiguity error), except an absent optional input, which is `None`.
    - MANY: every artifact of that stage among the DONE rows of the closure
      (plus the fresh row). An absent optional input is `[]`.

    `expected_types[i]`, when given, narrows input i to those model classes; it
    tells apart the artifact types of a stage that has several (Swot/Errc).
    """
    done = [r for r in rows.values() if r.status == StageStatus.DONE and r.id != fresh_row.id]
    direct = [rows[i] for ids in fresh_row.refs.values() for i in ids if i in rows]
    gathered: list[Any] = []
    for index, spec in enumerate(inputs):
        wanted = expected_types[index] if expected_types is not None else None

        def narrow(items: list[BaseModel], wanted: tuple[type, ...] | None = wanted) -> list[BaseModel]:
            return [a for a in items if isinstance(a, wanted)] if wanted else items

        if spec.arity == StageArity.ONE:
            pool = list(fresh_artifacts)
            for ref in direct:
                if ref.id != fresh_row.id:
                    pool.extend(parse_row_artifacts(ref))
            found = narrow(_of_stage(pool, spec.stage))
            if len(found) > 1:
                raise ContextError(
                    f"ambiguous input: {len(found)} {spec.stage.value} artifacts reachable from row "
                    f"{fresh_row.id}: {[getattr(a, 'id', '?') for a in found]}"
                )
            if not found:
                if spec.optional:
                    gathered.append(None)
                    continue
                raise ContextError(f"no {spec.stage.value} artifact reachable from row {fresh_row.id}")
            gathered.append(found[0])
        else:
            pool = list(fresh_artifacts)
            for other in done:
                pool.extend(parse_row_artifacts(other))
            found = narrow(_of_stage(pool, spec.stage))
            if not found and not spec.optional:
                raise ContextError(f"no {spec.stage.value} artifacts in the closure of row {fresh_row.id}")
            gathered.append(found)
    return gathered


def expected_types_of(rule: ConsistencyRule) -> list[tuple[type, ...] | None]:
    """Model classes each parameter of a rule's `check` is annotated with
    (`None` where the annotation names no model class)."""
    try:
        hints = typing.get_type_hints(rule.check)
    except Exception:
        return [None] * len(rule.inputs)
    names = [n for n in inspect.signature(rule.check).parameters]
    return [_classes(hints.get(name)) for name in names[: len(rule.inputs)]]


def _classes(annotation: Any) -> tuple[type, ...] | None:
    if annotation is None:
        return None
    origin = typing.get_origin(annotation)
    if origin in (list, Sequence):
        args = typing.get_args(annotation)
        return _classes(args[0]) if args else None
    if origin in (typing.Union, types.UnionType):
        classes = [c for arg in typing.get_args(annotation) if arg is not type(None) for c in (_classes(arg) or ())]
        return tuple(classes) or None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    return None
