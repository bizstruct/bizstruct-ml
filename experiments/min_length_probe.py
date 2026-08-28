"""Repeats the min_length provocation test (part B4) against a given
deployment: a structured-output schema requires a field of at least 40
characters while the system prompt instructs the model to reply with
nothing but the single word "ok". Previously observed (Aug 2026, against
gpt-5.6-sol): the model padded its own reply with an unrequested
explanation to satisfy `minLength=40` rather than following the
instruction literally.

This is a real, isolated API call — not routed through bizstruct-ml's
queue/worker pipeline — using the same openai SDK dependency already in
bizstruct-ml's pyproject.toml. Run directly (`python -m
experiments.min_length_probe --deployment <name>`) after switching to
the deployment under test (see deploy.py / cli.py), or point it at any
deployment via --endpoint/--api-key/--api-version without touching the
running worker at all.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from openai import AsyncAzureOpenAI
from pydantic import BaseModel, Field

PROVOCATION_SYSTEM_PROMPT = (
    "You must reply with exactly the single word 'ok'. Nothing else. "
    "No punctuation, no explanation, no additional words."
)
PROVOCATION_USER_PROMPT = "Confirm you're working."
MIN_LENGTH = 40


class ProbeSchema(BaseModel):
    message: str = Field(min_length=MIN_LENGTH)


async def run_probe(
    *, endpoint: str, api_key: str, api_version: str, deployment: str
) -> dict:
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint, api_key=api_key, api_version=api_version, timeout=60.0
    )
    messages = [
        {"role": "system", "content": PROVOCATION_SYSTEM_PROMPT},
        {"role": "user", "content": PROVOCATION_USER_PROMPT},
    ]

    result = {
        "deployment": deployment,
        "min_length": MIN_LENGTH,
        "outcome": None,
        "returned_message": None,
        "returned_length": None,
        "error": None,
    }

    try:
        completion = await client.beta.chat.completions.parse(
            model=deployment, messages=messages, response_format=ProbeSchema
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            refusal = completion.choices[0].message.refusal
            result["outcome"] = "refused" if refusal else "empty_parse"
            result["error"] = refusal
        else:
            result["returned_message"] = parsed.message
            result["returned_length"] = len(parsed.message)
            if parsed.message.strip().lower() == "ok":
                # Should be impossible if the schema was actually enforced
                # (len("ok") < MIN_LENGTH) — recorded distinctly in case a
                # future model/SDK version validates more loosely.
                result["outcome"] = "instruction_followed_schema_violated"
            elif len(parsed.message) >= MIN_LENGTH:
                result["outcome"] = "padded_to_satisfy_schema"
            else:
                result["outcome"] = "unexpected"
    except Exception as e:  # noqa: BLE001 - report any SDK/schema rejection as data, not a crash
        result["outcome"] = "api_error"
        result["error"] = str(e)
    finally:
        await client.close()

    return result


def _read_ml_env(env_path: Path) -> dict[str, str]:
    from experiments.run_meta import read_ml_env

    return read_ml_env(env_path)


async def main() -> None:
    parser = argparse.ArgumentParser(description="min_length provocation probe (part B4)")
    parser.add_argument("--deployment", required=True, help="Azure OpenAI deployment name to probe")
    parser.add_argument("--endpoint", default=None, help="Defaults to AZURE_OPENAI_ENDPOINT in bizstruct-ml/.env")
    parser.add_argument("--api-key", default=None, help="Defaults to AZURE_OPENAI_API_KEY in bizstruct-ml/.env")
    parser.add_argument("--api-version", default=None, help="Defaults to AZURE_OPENAI_API_VERSION in bizstruct-ml/.env")
    parser.add_argument("--env-file", type=Path, default=Path(__file__).parent.parent / ".env")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "min_length_probe.jsonl")
    args = parser.parse_args()

    env = _read_ml_env(args.env_file)
    endpoint = args.endpoint or env.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = args.api_key or env.get("AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    # Matches bizstruct_ml.config.Settings.azure_openai_api_version's own default.
    api_version = (
        args.api_version or env.get("AZURE_OPENAI_API_VERSION")
        or os.environ.get("AZURE_OPENAI_API_VERSION") or "2024-10-21"
    )

    if not endpoint or not api_key:
        raise SystemExit(
            "Missing endpoint/api-key — pass them explicitly or ensure "
            f"{args.env_file} has AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_KEY"
        )

    result = await run_probe(
        endpoint=endpoint, api_key=api_key, api_version=api_version, deployment=args.deployment
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False))
        f.write("\n")

    print(f"[min_length_probe] {args.deployment}: {result['outcome']}")
    if result["returned_message"] is not None:
        print(f"  returned ({result['returned_length']} chars): {result['returned_message']!r}")
    if result["error"]:
        print(f"  error: {result['error']}")
    print(f"[min_length_probe] appended to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
