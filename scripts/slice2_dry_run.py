"""Slice 2 dry run: brief -> empathy maps -> scenarios/ideations -> patterns -> one canvas per group,
with the REAL generator client against the in-memory fake backend (standing in for be).

The judge is the real one if JUDGE_* are configured (settings or environment), otherwise a
`FakeJudgeModel` that finds nothing; the first line of the output says which.

    uv run python scripts/slice2_dry_run.py "An app that delivers farm produce to city parents"
    uv run python scripts/slice2_dry_run.py --language uk --json out.json "Підписка на набори для домашнього пивоваріння"

Prints per run: the groups and the branch decision, the relation types, the pattern tags and the
pairwise scores, the interdependence_signal of EVERY scenario, the retries per row and what
triggered them, the tokens per stage, and then the canvases. Makes real, billable API calls: run
by hand, never by CI. Langfuse is switched off.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # slice1_dry_run (sets the dummy environment on import)

from bizstruct_domain.schemas import GENERATION_CONTRACTS, CustomerScenario, Patterns, Stage, parse_artifact  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from slice1_dry_run import UsageLLM, build_judge  # noqa: E402

from bizstruct_ml.core.stage_runner import RunOutcome, StageRunner  # noqa: E402
from bizstruct_ml.llm.client import LLMClient  # noqa: E402
from bizstruct_ml.stages import SLICE_2_GENERATORS  # noqa: E402
from tests.support.fake_backend import FakeBackend  # noqa: E402

STAGE_OF_CONTRACT = {c.__name__: stage for stage, contracts in GENERATION_CONTRACTS.items() for c in contracts}


@dataclass
class RowRecord:
    row_id: str
    stage: str
    calls: int = 0
    tokens: int = 0
    triggers: list[str] = field(default_factory=list)  # why each call after the first happened
    consistency_retries: int = 0
    failure: str | None = None


def trigger_of(messages: list[dict]) -> str | None:
    """What made this call a repeat, read off the last message the runner appended."""
    last = messages[-1]["content"]
    if last.startswith("Your previous answer was inconsistent"):
        return "consistency: " + last.split("answer again:\n", 1)[-1].replace("\n", " ")[:300]
    if last.startswith("Your previous answer could not be used"):
        return "conversion/structure: " + last.split("reason:\n", 1)[-1].split("\nFix it", 1)[0].replace("\n", " ")[:300]
    return None


@dataclass
class TrackingLLM(UsageLLM):
    current_row: str = ""
    rows: dict[str, RowRecord] = field(default_factory=dict)

    async def generate_structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        record = self.rows.setdefault(self.current_row, RowRecord(self.current_row, STAGE_OF_CONTRACT[schema.__name__].value))
        record.calls += 1
        reason = trigger_of(messages)
        if reason:
            record.triggers.append(reason)
        before = len(self.calls)
        try:
            return await super().generate_structured(messages, schema)
        finally:
            call = self.calls[before] if len(self.calls) > before else None
            if call is not None:
                record.tokens += (call.usage or {}).get("total", 0)
                if call.error:
                    record.triggers.append("llm error: " + call.error[:200])


class TrackingRunner(StageRunner):
    def __init__(self, *args, llm: TrackingLLM, **kwargs) -> None:
        super().__init__(*args, llm=llm, **kwargs)
        self.tracker = llm
        self.outcomes: dict[str, RunOutcome] = {}

    async def run(self, row, snapshot_closure, language) -> RunOutcome:
        self.tracker.current_row = row.id
        outcome = await super().run(row, snapshot_closure, language)
        self.outcomes[row.id] = outcome
        record = self.tracker.rows.setdefault(row.id, RowRecord(row.id, row.stage.value))
        record.consistency_retries = outcome.consistency_retries
        record.failure = outcome.failure.message if outcome.failure else None
        return outcome


def summarise(backend: FakeBackend, llm: TrackingLLM) -> dict:
    (patterns_row,) = backend.rows_of(Stage.PATTERNS) or [None]
    patterns = parse_artifact(patterns_row.artifacts[0]) if patterns_row and patterns_row.artifacts else None
    scenarios = []
    for row in backend.rows_of(Stage.CUSTOMER_SCENARIO):
        if row.artifacts:
            scenario = parse_artifact(row.artifacts[0])
            assert isinstance(scenario, CustomerScenario)
            scenarios.append({"row": row.id, "interdependence_signal": scenario.interdependence_signal,
                              "pricing_tier": scenario.pricing_tier.value if scenario.pricing_tier else None,
                              "channel_type": scenario.channel_type, "relationship_type": scenario.relationship_type})
    tokens: dict[str, dict[str, int]] = {}
    for call in llm.calls:
        stage = STAGE_OF_CONTRACT[call.schema].value
        bucket = tokens.setdefault(stage, {"input": 0, "output": 0, "total": 0, "calls": 0})
        bucket["calls"] += 1
        for key in ("input", "output", "total"):
            bucket[key] += (call.usage or {}).get(key, 0)
    summary: dict = {"scenarios": scenarios, "tokens_per_stage": tokens, "rows": {k: vars(v) for k, v in llm.rows.items()}}
    if isinstance(patterns, Patterns):
        index = {em_row.artifacts[0].id: i + 1 for i, em_row in enumerate(backend.rows_of(Stage.EMPATHY_MAP))}
        summary["branch_decision"] = patterns.branch_decision.value
        summary["groups"] = [{"segments": [f"S{index[i]}" for i in g.empathy_map_ids], "relation_type": g.relation_type.value} for g in patterns.groups]
        summary["pattern_tags"] = [{"pattern": t.pattern.value, "subtype": t.subtype.value if t.subtype else None, "rationale": t.rationale} for t in patterns.pattern_tags]
        summary["pairwise_scores"] = [
            {"pair": f"S{index[s.segment_pair.empathy_map_id_a]}-S{index[s.segment_pair.empathy_map_id_b]}", "synergy": s.synergy, "conflict": s.conflict}
            for s in patterns.pairwise_scores
        ]
    return summary


async def main(idea: str, language: str, json_path: str | None, *, inner=None, judge=None, judge_label: str = "") -> int:
    """`inner`, `judge` and `judge_label` are for the offline smoke test; by default the real ones are built."""
    llm = TrackingLLM(inner or LLMClient())
    if judge is None:
        judge, judge_label = build_judge()
    runner = TrackingRunner(SLICE_2_GENERATORS, llm=llm, judge=judge)
    backend = FakeBackend(idea=idea, language=language, through=Stage.CANVAS)
    print(f"generator: {llm.model_name}   judge: {judge_label}   language: {language}\nidea: {idea}\n")
    await backend.run_to_completion(runner)
    summary = summarise(backend, llm)

    if "groups" in summary:
        print(f"== Patterns: {summary['branch_decision']}, {len(summary['groups'])} group(s)")
        for i, g in enumerate(summary["groups"]):
            print(f"  group {i}: {', '.join(g['segments'])}  [{g['relation_type']}]")
        for s in summary["pairwise_scores"]:
            print(f"  {s['pair']}: synergy {s['synergy']}, conflict {s['conflict']}, net {s['synergy'] + s['conflict']}")
        print("  pattern tags: " + (", ".join(f"{t['pattern']}" + (f"/{t['subtype']}" if t["subtype"] else "") for t in summary["pattern_tags"]) or "none"))
        for t in summary["pattern_tags"]:
            print(f"    - {t['pattern']}: {t['rationale']}")
    print("\n== interdependence_signal per scenario")
    for s in summary["scenarios"]:
        print(f"  {s['row']}: {s['interdependence_signal']}  (tier {s['pricing_tier']}, channel {s['channel_type']}, relationship {s['relationship_type']})")
    print("\n== rows (calls beyond the first are retries)")
    for record in summary["rows"].values():
        extra = f"  retries: {record['triggers']}" if record["triggers"] else ""
        print(f"  {record['row_id']:<28} calls {record['calls']}  tokens {record['tokens']}  consistency retries {record['consistency_retries']}"
              + (f"  FAILED: {record['failure']}" if record["failure"] else "") + extra)
    print("\n== tokens per stage")
    for stage, bucket in summary["tokens_per_stage"].items():
        print(f"  {stage:<18} calls {bucket['calls']:>2}  in {bucket['input']:>6}  out {bucket['output']:>6}  total {bucket['total']:>6}")
    total = sum(b["total"] for b in summary["tokens_per_stage"].values())
    print(f"  {'ALL':<18} total {total}")

    for row in backend.rows_of(Stage.CANVAS):
        print(f"\n===== {row.id} [{row.status.value}]")
        if row.artifacts:
            sections = row.artifacts[0].data["sections"]
            for name, cards in sections.items():
                print(f"  {name}:")
                for card in cards:
                    print(f"    - {card['text']}")
        if row.consistency is not None:
            print(f"  consistency: score {row.consistency.score}")
            for v in row.consistency.violations:
                print(f"    [{v.severity}] {v.rule_id}: {v.message}")
    patterns_row = (backend.rows_of(Stage.PATTERNS) or [None])[0]
    if patterns_row is not None and patterns_row.consistency is not None:
        print(f"\npatterns consistency: score {patterns_row.consistency.score}")
        for v in patterns_row.consistency.violations:
            print(f"  [{v.severity}] {v.rule_id}: {v.message}")

    failed = [r for r in backend.posted if r.status == "failed"]
    for result in failed:
        print(f"!!! {result.stage_row_id} FAILED: {result.error.message if result.error else ''}")
    ok = all(r.status.value == "done" for r in backend.rows.values()) and not failed
    if json_path:
        Path(json_path).write_text(json.dumps({"idea": idea, "language": language, "judge": judge_label, "ok": ok, **summary,
                                               "canvases": [r.artifacts[0].data for r in backend.rows_of(Stage.CANVAS) if r.artifacts]},
                                              ensure_ascii=False, indent=1))
    print(f"\nrows: {len(backend.rows)}  result: {'OK' if ok else 'PROBLEMS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("idea")
    parser.add_argument("--language", default="en", choices=["en", "uk"])
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.idea, args.language, args.json_path)))
