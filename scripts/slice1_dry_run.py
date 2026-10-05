"""Slice 1 dry run: first contact of the prompts and generation JSON Schemas with a real model.

Runs the in-memory fake backend (`tests/support/fake_backend.py`, standing in for
be) with the REAL generator client, so the Brief for an idea goes through every
empathy_map row to the customer_scenario and ideation rows. The judge is the real
one if JUDGE_* are configured (settings or environment), otherwise a
`FakeJudgeModel` that finds nothing.

    uv run python scripts/slice1_dry_run.py "An app that delivers farm produce to city parents"
    uv run python scripts/slice1_dry_run.py --language uk "Застосунок для доставки фермерських продуктів"

Prints every artifact, the token usage of every LLM call, and any API error: a
rejection of a generation JSON Schema (date formats, integer enums, nested $defs,
minItems/maxItems, ...) shows up as the error text of the failed call.

`--probe-schemas` instead sends EVERY stage's generation contract (not just slice 1)
to the API with a tiny output cap and reports which schemas the API accepts: a schema
rejection is a request-time 400, so this finds unsupported keywords (date formats,
integer enums, nested $defs, minItems/maxItems, ...) for the stages not built yet
without paying for full outputs.

Makes real, billable API calls: run by hand, never by CI. The pytest wrapper
(tests/test_slice1_live.py) is marked `live` and skipped by default. Langfuse is
switched off for this run.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Before bizstruct_ml.config is imported: no traces from a dry run, and dummy values
# for the settings this script does not use, so a bare environment still loads.
for _name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
    os.environ[_name] = ""
os.environ.setdefault("SERVICE_BUS_CONNECTION_STRING", "Endpoint=sb://dry-run/;SharedAccessKeyName=x;SharedAccessKey=eA==")
os.environ.setdefault("SERVICE_BUS_QUEUE_NAME", "dry-run")
os.environ.setdefault("BACKEND_BASE_URL", "http://dry-run.invalid")
os.environ.setdefault("BACKEND_API_KEY", "dry-run")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tests.support

from pydantic import BaseModel  # noqa: E402

from bizstruct_ml.config import settings  # noqa: E402
from bizstruct_ml.core.stage_runner import StageRunner  # noqa: E402
from bizstruct_ml.judge.base import ConsistencyJudge  # noqa: E402
from bizstruct_ml.judge.factory import build_judge_model  # noqa: E402
from bizstruct_ml.judge.fake import FakeJudgeModel  # noqa: E402
from bizstruct_ml.judge.guard import assert_different_family  # noqa: E402
from bizstruct_ml.llm.client import GENERATOR_FAMILY, LLMClient, LLMError  # noqa: E402
from bizstruct_ml.stages import SLICE_1_GENERATORS  # noqa: E402
from tests.support.fake_backend import FakeBackend  # noqa: E402

DEFAULT_IDEA = "An app that delivers boxes of fresh produce from local farms to busy city parents."


@dataclass
class CallRecord:
    schema: str
    seconds: float
    usage: dict[str, int] | None
    error: str | None


@dataclass
class UsageLLM:
    """Wraps the real client: records usage and errors of every call."""

    inner: LLMClient
    calls: list[CallRecord] = field(default_factory=list)
    last_usage: dict[str, int] | None = None

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    async def generate_structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        start = time.monotonic()
        try:
            result = await self.inner.generate_structured(messages, schema)
        except LLMError as e:
            self.calls.append(CallRecord(schema.__name__, time.monotonic() - start, None, str(e)))
            raise
        self.last_usage = self.inner.last_usage
        self.calls.append(CallRecord(schema.__name__, time.monotonic() - start, self.inner.last_usage, None))
        return result


def build_judge() -> tuple[ConsistencyJudge, str]:
    if settings.judge_endpoint and settings.judge_api_key and settings.judge_deployment:
        model = build_judge_model(settings)
        assert_different_family(GENERATOR_FAMILY, model.family)
        return ConsistencyJudge(model), f"real judge ({settings.judge_provider}, {settings.judge_deployment})"
    return ConsistencyJudge(FakeJudgeModel([json.dumps({"score": 5, "violations": []})])), "FakeJudgeModel (no JUDGE_* configured)"


async def probe_schemas() -> int:
    """Send every generation contract to the API with a tiny output cap."""
    from bizstruct_domain.schemas import GENERATION_CONTRACTS
    from openai import APIError, LengthFinishReasonError

    client = LLMClient()
    rejected = 0
    print(f"generator: {client.model_name}\n")
    for stage, contracts in GENERATION_CONTRACTS.items():
        for contract in contracts:
            try:
                await client._client.beta.chat.completions.parse(
                    model=client.model_name,
                    messages=[{"role": "user", "content": "Fill the schema with minimal plausible values."}],
                    response_format=contract,
                    max_completion_tokens=16,
                )
                verdict = "accepted"
            except LengthFinishReasonError:
                verdict = "accepted (output cut off by the cap, as intended)"
            except APIError as e:
                verdict, rejected = f"REJECTED: {e}", rejected + 1
            print(f"{stage.value:<18} {contract.__name__:<26} {verdict}")
    print(f"\n{rejected} rejected")
    return 1 if rejected else 0


async def main(idea: str, language: str) -> int:
    llm = UsageLLM(LLMClient())
    judge, judge_label = build_judge()
    runner = StageRunner(SLICE_1_GENERATORS, llm, judge)
    backend = FakeBackend(idea=idea, language=language)

    print(f"generator: {llm.model_name}   judge: {judge_label}   language: {language}")
    print(f"idea: {idea}\n")
    dispositions = await backend.run_to_completion(runner)

    for row in sorted(backend.rows.values(), key=lambda r: (r.stage.value, r.instance_index)):
        print(f"===== {row.id}  [{row.status.value}]" + (f"  error: {row.error}" if row.error else ""))
        for record in row.artifacts:
            print(f"--- {record.type} {record.id}")
            print(json.dumps(record.data, ensure_ascii=False, indent=2))
        if row.consistency is not None:
            print(f"--- consistency: score {row.consistency.score}")
            for v in row.consistency.violations:
                print(f"    [{v.severity}] {v.rule_id}: {v.message}")
        print()

    failed = [r for r in backend.posted if r.status == "failed"]
    for result in failed:
        print(f"!!! {result.stage_row_id} FAILED: {result.error.message if result.error else ''}\n")

    print("== LLM calls")
    total = {"input": 0, "output": 0, "total": 0}
    for i, call in enumerate(llm.calls, 1):
        usage = call.usage or {}
        for key in total:
            total[key] += usage.get(key, 0)
        print(f"{i:>2}. {call.schema:<28} {call.seconds:5.1f}s  tokens {usage or '-'}" + (f"  ERROR: {call.error}" if call.error else ""))
    print(f"total tokens: {total}")

    errors = sorted({c.error for c in llm.calls if c.error})
    if errors:
        print("\n== API errors (what the structured output rejected)")
        for error in errors:
            print(f"- {error}")
    ok = all(r.status.value == "done" for r in backend.rows.values()) and not failed
    print(f"\nrows: {len(backend.rows)}  dispositions: {[d.reason for d in dispositions]}  result: {'OK' if ok else 'PROBLEMS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("idea", nargs="?", default=DEFAULT_IDEA)
    parser.add_argument("--language", default="en", choices=["en", "uk"])
    parser.add_argument("--probe-schemas", action="store_true", help="only check which generation schemas the API accepts")
    args = parser.parse_args()
    sys.exit(asyncio.run(probe_schemas() if args.probe_schemas else main(args.idea, args.language)))
