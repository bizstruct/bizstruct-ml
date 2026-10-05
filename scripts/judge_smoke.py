"""Live smoke test of the judge deployment.

Reads JUDGE_ENDPOINT, JUDGE_API_KEY, JUDGE_DEPLOYMENT (and optionally
JUDGE_TIMEOUT_SECONDS) from the environment, sends one tiny JudgeCheck-style
request through ConsistencyJudge, and prints the raw response and the parsed
report. Then it probes what the deployment accepts: JSON mode, temperature=0 and
max tokens, each tried on its own, so the settings JUDGE_JSON_MODE and
JUDGE_MAX_TOKENS can be set from evidence rather than assumption.

    uv run python scripts/judge_smoke.py

Makes real API calls. Run by the maintainer, never by CI (the pytest wrapper is
marked `live` and skipped by default).
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import ClassVar

from bizstruct_domain.schemas import ConsistencyReport, JudgeCheck, RuleInput, Stage, StageArity

from bizstruct_ml.judge.azure_foundry import AzureFoundryChatJudge
from bizstruct_ml.judge.base import ConsistencyJudge, JudgeModel, JudgeModelError

CHECK = JudgeCheck(
    id="smoke_persona_consistency",
    inputs=(
        RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),
        RuleInput(stage=Stage.CUSTOMER_SCENARIO, arity=StageArity.ONE),
    ),
    instruction=(
        "You will see one empathy map and the customer scenario for the same persona. "
        "Report a violation if the scenario shows the persona doing confidently and without friction "
        "something the empathy map lists as a pain. Omission is not a contradiction."
    ),
)
INPUTS = [
    {"id": "em-1", "persona_name": "Olena", "pains": ["Finds mobile banking apps confusing and avoids them"]},
    {"id": "cs-1", "situation_narrative": "Olena opens her banking app and effortlessly pays three bills in a minute."},
]


class RecordingJudge(JudgeModel):
    family: ClassVar[str] = "recording"

    def __init__(self, inner: AzureFoundryChatJudge) -> None:
        self._inner = inner
        self.raw: str | None = None

    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.raw = await self._inner.complete_json(system=system, user=user, temperature=temperature)
        return self.raw


@dataclass
class SmokeResult:
    raw: str | None
    report: ConsistencyReport | None
    error: str | None


def build_judge(*, json_mode: bool = False, max_tokens: int | None = None) -> AzureFoundryChatJudge:
    return AzureFoundryChatJudge(
        endpoint=os.environ["JUDGE_ENDPOINT"],
        api_key=os.environ["JUDGE_API_KEY"],
        deployment=os.environ["JUDGE_DEPLOYMENT"],
        timeout_seconds=float(os.environ.get("JUDGE_TIMEOUT_SECONDS", "60")),
        json_mode=json_mode,
        max_tokens=max_tokens,
    )


async def run_smoke(*, json_mode: bool = False, max_tokens: int | None = None) -> SmokeResult:
    recording = RecordingJudge(build_judge(json_mode=json_mode, max_tokens=max_tokens))
    try:
        report = await ConsistencyJudge(recording, max_attempts=1).evaluate(CHECK, INPUTS)
    except Exception as e:  # report every failure mode, do not stop the probe
        return SmokeResult(raw=recording.raw, report=None, error=f"{type(e).__name__}: {e}")
    return SmokeResult(raw=recording.raw, report=report, error=None)


async def main() -> int:
    missing = [n for n in ("JUDGE_ENDPOINT", "JUDGE_API_KEY", "JUDGE_DEPLOYMENT") if not os.environ.get(n)]
    if missing:
        print(f"missing environment: {', '.join(missing)}", file=sys.stderr)
        return 2

    base = await run_smoke()
    print("== baseline (temperature=0, no JSON mode, no max_tokens) ==")
    print("raw response:\n", base.raw)
    print("parsed report:\n", base.report.model_dump_json(indent=2) if base.report else None)
    print("error:", base.error)

    print("\n== probe: what the deployment accepts ==")
    probes = {
        "temperature=0 (baseline)": base,
        "JSON mode (response_format=json_object)": await run_smoke(json_mode=True),
        "max_tokens=800": await run_smoke(max_tokens=800),
    }
    for name, result in probes.items():
        accepted = result.error is None or "judge API error" not in result.error
        print(f"{name}: {'accepted' if accepted else 'REJECTED'}  parsed={'yes' if result.report else 'no'}  {result.error or ''}")
    print("\nSet JUDGE_JSON_MODE=true / JUDGE_MAX_TOKENS=800 only for the options marked accepted.")
    return 0 if base.report else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
