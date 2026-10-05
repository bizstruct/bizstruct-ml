"""Judge abstraction, two layers.

`JudgeModel` is the provider layer: one method that sends a system prompt and a
user prompt to some chat model and returns its raw text. A new provider is one
subclass.

`ConsistencyJudge` is the protocol layer, identical for every provider: it
turns a domain `JudgeCheck` plus the gathered artifacts into a prompt, parses
the answer as a `ConsistencyReport`, retries on garbage and raises
`JudgeUnavailable` when the judge cannot produce a usable report.
"""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

import structlog
from bizstruct_domain.schemas import ConsistencyReport, JudgeCheck
from pydantic import BaseModel, ValidationError

from bizstruct_ml.llm.retry import retry_async

log = structlog.get_logger()

# Whether judge findings may carry severity "error" (blocking `DONE` in be).
# Pending ADR-0011 open question 5: until the maintainer decides which judge
# findings are blocking, every finding is capped at "warning" — advisory only.
JUDGE_BLOCKING = False

OUTPUT_FORMAT = """\
Output format. Reply with valid JSON only: no prose, no markdown fences.
The JSON object has exactly these fields:
- "score": integer from 1 (severely inconsistent) to 5 (fully consistent).
- "violations": array of objects, empty if you found nothing. Each object has:
  - "rule_id": the id of the check you are performing.
  - "severity": "error" or "warning".
  - "message": what is wrong, specific enough to act on.
  - "artifact_ids": non-empty array of artifact ids, copied exactly from the
    "id" fields of the data you were given; never invent an id.
Report only what the instructions above ask you to check."""


class JudgeModelError(Exception):
    """The provider call failed (transport, timeout, API error). Retryable."""


class InvalidJudgeOutput(Exception):
    """The judge answered, but not with a valid `ConsistencyReport`. Retryable."""


class JudgeUnavailable(Exception):
    """The judge could not produce a usable report after all retries."""


class JudgeModel(ABC):
    """Provider layer: raw chat completion that should return JSON text."""

    # Model family, compared against the generator's family at startup.
    family: ClassVar[str]

    @abstractmethod
    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        """Return the model's raw reply. Raise `JudgeModelError` on provider failure."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _input_ids(inputs: Sequence[Any]) -> list[str]:
    """Ids of the provided inputs, in order, without duplicates. Inputs without an
    `id` (a Brief, an absent optional input) contribute nothing."""
    ids: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                add(item)
            return
        artifact_id = value.get("id") if isinstance(value, dict) else getattr(value, "id", None)
        if isinstance(artifact_id, str) and artifact_id not in ids:
            ids.append(artifact_id)

    for value in inputs:
        add(value)
    return ids


def _ground(report: ConsistencyReport, check: JudgeCheck, inputs: Sequence[Any]) -> ConsistencyReport:
    """Make a judge report trustworthy about what it cites.

    Every violation gets `rule_id = check.id` (the model may not echo it right).
    Cited artifact ids that are not ids of the provided inputs are dropped; if
    none remain the violation cites all provided ids instead, and if the inputs
    carry no id at all the violation is dropped (and logged): it could not be
    attributed to any artifact.
    """
    known = _input_ids(inputs)
    kept = []
    for violation in report.violations:
        cited = [i for i in violation.artifact_ids if i in known]
        if not cited:
            cited = list(known)
        if not cited:
            log.warning("judge_violation_dropped", check_id=check.id, message=violation.message)
            continue
        kept.append(violation.model_copy(update={"rule_id": check.id, "artifact_ids": cited}))
    return report.model_copy(update={"violations": kept})


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_fence(raw: str) -> str:
    match = _FENCE.match(raw)
    return match.group(1) if match else raw


class ConsistencyJudge:
    """Protocol layer: run a `JudgeCheck` on a `JudgeModel`."""

    def __init__(self, model: JudgeModel, *, max_attempts: int = 3, retry_wait: float = 2.0) -> None:
        self._model = model
        self._max_attempts = max_attempts
        self._retry_wait = retry_wait

    @staticmethod
    def build_prompts(check: JudgeCheck, inputs: Sequence[Any]) -> tuple[str, str]:
        """(system, user): the check's instruction plus the fixed output format,
        and the inputs as JSON labelled by each input's stage."""
        if len(inputs) != len(check.inputs):
            raise ValueError(f"{check.id} takes {len(check.inputs)} inputs, got {len(inputs)}")
        system = f"{check.instruction}\n\n{OUTPUT_FORMAT}\n\nThe id of this check is \"{check.id}\"."
        payload = {spec.stage.value: _jsonable(value) for spec, value in zip(check.inputs, inputs, strict=True)}
        return system, json.dumps(payload, ensure_ascii=False, indent=2)

    async def evaluate(self, check: JudgeCheck, inputs: Sequence[Any]) -> ConsistencyReport:
        system, user = self.build_prompts(check, inputs)

        async def attempt() -> ConsistencyReport:
            raw = await self._model.complete_json(system=system, user=user, temperature=0.0)
            try:
                return ConsistencyReport.model_validate_json(_strip_fence(raw))
            except ValidationError as e:
                raise InvalidJudgeOutput(f"{check.id}: {e.error_count()} validation errors in judge reply") from e

        try:
            report = await retry_async(
                attempt,
                retry_on=(JudgeModelError, InvalidJudgeOutput),
                attempts=self._max_attempts,
                wait_min=self._retry_wait,
                wait_max=self._retry_wait,
            )
        except (JudgeModelError, InvalidJudgeOutput) as e:
            log.warning("judge_unavailable", check_id=check.id, error=str(e))
            raise JudgeUnavailable(f"{check.id}: {e}") from e

        report = _ground(report, check, inputs)
        if not JUDGE_BLOCKING:
            report = report.model_copy(
                update={"violations": [v.model_copy(update={"severity": "warning"}) for v in report.violations]}
            )
        return report
