"""Live positive and negative controls for the judge checks, on the real artifacts of one project.

For each judge check the script runs the ORIGINAL inputs (expected: no violation, a violation
is a false alarm) and a deliberately BROKEN variant (expected: a violation, no violation is a
miss), several times each. It also shows the split between the judge and the deterministic
rules with one broken ERRC move, which `errc_move_targets_correct_canvas_version` catches
without any model.

    uv run python scripts/judge_controls.py --project smoke-dumps/coffee-20261027.json --repeats 3

Reads JUDGE_ENDPOINT, JUDGE_API_KEY, JUDGE_DEPLOYMENT (and the optional JUDGE_* settings that
scripts/judge_smoke.py documents) from the environment; nothing is printed or written that
contains them. Makes real API calls, so it is run by hand and never by CI (the pytest wrapper
is marked `live`).

The cases are fixed by the code below, in the project's language. The judge prompts are the
domain's, untouched: a case that is missed is reported as missed, not fixed by tuning.
The sample is small (a few cases times a few repeats on one project): it shows whether the
judge can tell a clear break from the original at all, not how often it is right.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bizstruct_domain.schemas import (
    CONSISTENCY_RULES,
    JUDGE_CHECKS,
    ArtifactType,
    ConsistencyViolation,
    JudgeCheck,
    bind_inputs,
)
from bizstruct_domain.schemas.wire import ArtifactRecord
from bizstruct_domain.schemas import parse_artifact
from pydantic import BaseModel

from bizstruct_ml.judge.azure_foundry import AzureFoundryChatJudge
from bizstruct_ml.judge.base import ConsistencyJudge, JudgeUnavailable

PERSONA_CHECK = "empathy_map_customer_scenario_persona_consistency"
PITCH_CHECK = "pitch_risk_analysis_grounded_in_swot"
ERRC_RULE = "errc_move_targets_correct_canvas_version"

# A different persona than the project's (a coffee-shop owner), written to be plainly someone else.
OTHER_PERSONA_NARRATIVE = (
    "Тарас Бондаренко, 58 років, директор з логістики великого агрохолдингу під Полтавою, у вівторок зранку "
    "складає графік вивезення зерна з елеваторів на експорт. Він працює з диспетчерською системою на 140 вантажівок, "
    "щодня погоджує рейси з портами та залізницею й відповідає за штрафи за простій суден. "
    "Кав'ярень і випічки в його роботі немає: усі рішення стосуються тоннажу, тарифів на перевезення та термінів "
    "поставки за контрактами."
)

# Risks with no basis in the project's SWOT: a different industry, nothing about the product.
UNRELATED_RISKS = [
    "Різке подорожчання нафти на світових ринках може зробити перевезення вантажів непридатними для прибутку.",
    "Землетруси в сейсмічно активних регіонах можуть пошкодити склади та порушити роботу портів.",
    "Різка зміна курсу криптовалют може знецінити частину резервів, яку компанія тримає у цифрових активах.",
    "Страйк працівників авіакомпаній може затримати доставку обладнання для гірничодобувних шахт.",
]

BROKEN_CARD_TEXT = "Картка, якої немає на канвасі: безкоштовні космічні подорожі для кожного клієнта"


@dataclass
class Case:
    name: str
    check_id: str
    expect_violation: bool
    inputs: tuple[Any, ...]
    note: str = ""


@dataclass
class CaseResult:
    case: Case
    counts: list[int] = field(default_factory=list)  # violations per repeat; -1 = judge unavailable
    latencies: list[float] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def hits(self) -> int:
        """Repeats that came out as expected."""
        return sum(1 for c in self.counts if c >= 0 and (c > 0) == self.case.expect_violation)

    @property
    def unavailable(self) -> int:
        return sum(1 for c in self.counts if c < 0)


def load_artifacts(project: dict[str, Any]) -> dict[ArtifactType, list[BaseModel]]:
    """Every artifact of a done row, parsed with the domain's persisted models, by type."""
    by_type: dict[ArtifactType, list[BaseModel]] = {}
    for row in project["rows"]:
        if row["status"] != "done":
            continue
        for raw in row["artifacts"]:
            record = ArtifactRecord(id=raw["id"], type=raw["type"], data=raw["data"])
            by_type.setdefault(record.type, []).append(parse_artifact(record))
    return by_type


def check(check_id: str) -> JudgeCheck:
    return next(c for c in JUDGE_CHECKS if c.id == check_id)


def build_cases(artifacts: dict[ArtifactType, list[BaseModel]]) -> list[Case]:
    """Original and broken inputs for the persona and pitch checks, from the project's own artifacts."""
    persona = check(PERSONA_CHECK)
    pitch = check(PITCH_CHECK)
    (persona_args,) = bind_inputs(persona.inputs, artifacts)
    (pitch_args,) = bind_inputs(pitch.inputs, artifacts)
    empathy_map, scenario = persona_args
    swot, pitch_artifact = pitch_args

    other_persona = scenario.model_copy(update={"situation_narrative": OTHER_PERSONA_NARRATIVE})
    name = empathy_map.persona_name
    first_name = name.split()[0]
    renamed = scenario.model_copy(
        update={"situation_narrative": scenario.situation_narrative.replace(name, "Тарас Бондаренко").replace(first_name, "Тарас")}
    )
    unrelated_pitch = pitch_artifact.model_copy(update={"risk_analysis": UNRELATED_RISKS})

    return [
        Case("persona: original pair", PERSONA_CHECK, False, (empathy_map, scenario)),
        Case(
            "persona: scenario of a different persona", PERSONA_CHECK, True, (empathy_map, other_persona),
            "narrative rewritten for a logistics director; the empathy map is unchanged",
        ),
        Case(
            "persona: only the name swapped", PERSONA_CHECK, True, (empathy_map, renamed),
            "the subtle case: same life details, another name",
        ),
        Case("pitch: original risks", PITCH_CHECK, False, (swot, pitch_artifact)),
        Case(
            "pitch: risks unrelated to the SWOT", PITCH_CHECK, True, (swot, unrelated_pitch),
            "risk_analysis replaced by risks of another industry",
        ),
    ]


def errc_split(artifacts: dict[ArtifactType, list[BaseModel]]) -> tuple[list[ConsistencyViolation], list[ConsistencyViolation]]:
    """The deterministic rule on the first ERRC: as generated, and with one move pointed at a card that does not exist."""
    rule = next(r for r in CONSISTENCY_RULES if r.id == ERRC_RULE)
    canvases = artifacts[ArtifactType.CANVAS]
    errc = next(e for e in artifacts[ArtifactType.ERRC] if any(m.target_card_text for m in e.moves))
    index = next(i for i, m in enumerate(errc.moves) if m.target_card_text)
    moves = list(errc.moves)
    moves[index] = moves[index].model_copy(update={"target_card_text": BROKEN_CARD_TEXT})
    broken = errc.model_copy(update={"moves": moves})
    return rule.check(canvases, errc), rule.check(canvases, broken)


async def run_case(judge: ConsistencyJudge, case: Case, repeats: int) -> CaseResult:
    result = CaseResult(case)
    for _ in range(repeats):
        started = time.monotonic()
        try:
            report = await judge.evaluate(check(case.check_id), case.inputs)
        except JudgeUnavailable as error:
            result.counts.append(-1)
            result.messages.append(f"judge unavailable: {error}")
        else:
            result.counts.append(len(report.violations))
            result.messages.extend(v.message for v in report.violations)
        result.latencies.append(time.monotonic() - started)
    return result


def summarize(results: Sequence[CaseResult]) -> dict[str, int]:
    originals = [r for r in results if not r.case.expect_violation]
    broken = [r for r in results if r.case.expect_violation]
    return {
        "false_alarms": sum(c > 0 for r in originals for c in r.counts),
        "original_runs": sum(len(r.counts) for r in originals),
        "detected": sum(c > 0 for r in broken for c in r.counts),
        "broken_runs": sum(len(r.counts) for r in broken),
        "unavailable": sum(r.unavailable for r in results),
    }


def report(results: Sequence[CaseResult], split: tuple[list[ConsistencyViolation], list[ConsistencyViolation]]) -> None:
    print("== judge checks ==")
    for r in results:
        want = "violation" if r.case.expect_violation else "no violation"
        print(f"- {r.case.name} (expected: {want}): as expected {r.hits}/{len(r.counts)}, violations per repeat {r.counts}")
        if r.case.note:
            print(f"    {r.case.note}")
        for message in dict.fromkeys(r.messages):
            print(f"    judge says: {message[:300]}")
    s = summarize(results)
    print(
        f"\ndetection: {s['detected']}/{s['broken_runs']} broken runs flagged; "
        f"false alarms: {s['false_alarms']}/{s['original_runs']} original runs flagged; "
        f"judge unavailable: {s['unavailable']}"
    )
    latencies = sorted(x for r in results for x in r.latencies)
    if latencies:
        print(f"latency per call: median {latencies[len(latencies) // 2]:.1f} s, max {latencies[-1]:.1f} s")
    print("sample size: small (a few cases, a few repeats, one project); read it as a sanity check, not a rate.")

    original, broken = split
    print(f"\n== deterministic rule {ERRC_RULE} (no model, one run each) ==")
    print(f"- original ERRC: {len(original)} violations (expected 0)")
    print(f"- ERRC with a move pointed at a card that does not exist: {len(broken)} violations (expected >= 1)")
    for v in broken:
        print(f"    rule says: {v.message[:300]}")


def build_judge() -> AzureFoundryChatJudge:
    return AzureFoundryChatJudge(
        endpoint=os.environ["JUDGE_ENDPOINT"],
        api_key=os.environ["JUDGE_API_KEY"],
        deployment=os.environ["JUDGE_DEPLOYMENT"],
        timeout_seconds=float(os.environ.get("JUDGE_TIMEOUT_SECONDS", "60")),
        json_mode=os.environ.get("JUDGE_JSON_MODE", "").lower() == "true",
        max_tokens=int(os.environ["JUDGE_MAX_TOKENS"]) if os.environ.get("JUDGE_MAX_TOKENS") else None,
    )


async def amain(args: argparse.Namespace) -> int:
    missing = [n for n in ("JUDGE_ENDPOINT", "JUDGE_API_KEY", "JUDGE_DEPLOYMENT") if not os.environ.get(n)]
    if missing:
        print(f"missing environment: {', '.join(missing)}", file=sys.stderr)
        return 2
    project = json.loads(args.project.read_text())
    artifacts = load_artifacts(project)
    cases = build_cases(artifacts)
    model = build_judge()
    try:
        judge = ConsistencyJudge(model, max_attempts=1)  # one attempt: a failed call must show, not be retried away
        results = [await run_case(judge, case, args.repeats) for case in cases]
    finally:
        await model.aclose()
    report(results, errc_split(artifacts))
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True, help="project dump: {rows: [{status, artifacts: [{id, type, data}]}]}")
    parser.add_argument("--repeats", type=int, default=3)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(amain(parse_args())))
