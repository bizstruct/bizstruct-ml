"""Token usage of a project read back from the Langfuse public API, and the ledger it is compared with."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from bizstruct_domain import Stage

from experiments.client import SmokeError

LEDGER_PATH = Path(__file__).resolve().parent.parent / "docs" / "token-ledger.md"
DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"


@dataclass
class StageUsage:
    input: int = 0
    output: int = 0
    total: int = 0
    calls: int = 0


@dataclass
class LangfuseUsage:
    per_stage: dict[str, StageUsage] = field(default_factory=dict)
    traces: int = 0
    rows_traced: int = 0  # distinct row ids seen in the traces' metadata

    @property
    def total(self) -> int:
        return sum(u.total for u in self.per_stage.values())


def langfuse_settings(environ: Any = os.environ) -> tuple[str, str, str] | None:
    """(public key, secret key, host) from the environment, or None when the keys are not both set."""
    public, secret = environ.get("LANGFUSE_PUBLIC_KEY"), environ.get("LANGFUSE_SECRET_KEY")
    if not public or not secret:
        return None
    return public, secret, (environ.get("LANGFUSE_HOST") or DEFAULT_LANGFUSE_HOST).rstrip("/")


LANGFUSE_RATE_LIMIT_RETRIES = 8


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any], sleep: Callable[[float], Awaitable[None]]) -> httpx.Response:
    """GET that waits and tries again on 429 (Langfuse rate-limits its public API), honouring Retry-After."""
    for attempt in range(1, LANGFUSE_RATE_LIMIT_RETRIES + 1):
        response = await client.get(path, params=params)
        if response.status_code != 429 or attempt == LANGFUSE_RATE_LIMIT_RETRIES:
            return response
        retry_after = response.headers.get("retry-after", "")
        await sleep(min(float(retry_after), 60.0) if retry_after.replace(".", "", 1).isdigit() else min(2.0 * attempt, 30.0))
    raise AssertionError("unreachable")


async def _pages(client: httpx.AsyncClient, path: str, params: dict[str, Any], sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> list[dict[str, Any]]:
    """Every item of a paginated Langfuse list endpoint ({"data": [...], "meta": {"totalPages": n}})."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        response = await _get(client, path, {**params, "page": page, "limit": 100}, sleep)
        if response.status_code != 200:
            raise SmokeError(f"Langfuse answered HTTP {response.status_code} for {path}")
        body = response.json()
        items += body["data"]
        if page >= (body.get("meta") or {}).get("totalPages", 1):
            return items
        page += 1


def _usage_of(observation: dict[str, Any]) -> tuple[int, int, int]:
    """(input, output, total) of a generation: `usageDetails` if present, else the older `usage` object."""
    details = observation.get("usageDetails") or observation.get("usage") or {}
    inp, out = int(details.get("input") or 0), int(details.get("output") or 0)
    return inp, out, int(details.get("total") or (inp + out))


async def fetch_langfuse_usage(
    project_id: str,
    *,
    host: str,
    public_key: str,
    secret_key: str,
    expected_traces: int,
    wait: float = 90.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LangfuseUsage:
    """Tokens of the generator calls of one project, per stage. A trace is one queue message (session = project id,
    metadata.block = stage); its `llm_call` generations carry the usage. Langfuse ingests asynchronously, so the
    traces are read again for up to `wait` seconds until there are at least `expected_traces` (one per row)."""
    auth = httpx.BasicAuth(public_key, secret_key)
    async with httpx.AsyncClient(base_url=host, auth=auth, timeout=30.0, transport=transport) as client:
        waited = 0.0
        while True:
            traces = await _pages(client, "/api/public/traces", {"sessionId": project_id}, sleep)
            if len(traces) >= expected_traces or waited >= wait:
                break
            await sleep(5.0)
            waited += 5.0
        usage = LangfuseUsage(traces=len(traces))
        rows: set[str] = set()
        for trace in traces:
            metadata = trace.get("metadata") or {}
            stage = metadata.get("block") or next((t for t in trace.get("tags") or [] if t in {x.value for x in Stage}), "unknown")
            if metadata.get("row_id"):
                rows.add(metadata["row_id"])
            observations = await _pages(client, "/api/public/observations", {"traceId": trace["id"], "type": "GENERATION"}, sleep)
            bucket = usage.per_stage.setdefault(stage, StageUsage())
            for observation in observations:
                inp, out, total = _usage_of(observation)
                bucket.input += inp
                bucket.output += out
                bucket.total += total
                bucket.calls += 1
        usage.rows_traced = len(rows)
        return usage


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, list[int]]:
    """The measured per-run totals in docs/token-ledger.md, keyed by stage name, plus "ALL" for whole runs.

    Reads the markdown tables by header: a `stage` column with a `total` column (slices 1, 2 and 4), the cycle
    table (`idea` + `iterations` + `total`, recorded as swot_errc_cycle) and the whole-run table (`total tokens`)."""
    found: dict[str, list[int]] = {}
    header: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            header = []
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not header:
            header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue

        def number(column: str) -> int | None:
            if column not in header:
                return None
            text = cells[header.index(column)].replace(",", "")
            return int(text) if text.isdigit() else None

        if header[0] == "stage" and number("total") is not None:
            found.setdefault(cells[0], []).append(number("total"))  # type: ignore[arg-type]
        elif header[0] == "idea" and "iterations" in header and number("total") is not None:
            found.setdefault("swot_errc_cycle", []).append(number("total"))  # type: ignore[arg-type]
        elif header[0] == "idea" and number("total tokens") is not None:
            found.setdefault("ALL", []).append(number("total tokens"))  # type: ignore[arg-type]
    return found


def usage_report(usage: LangfuseUsage, ledger: dict[str, list[int]], rows_expected: int) -> list[str]:
    def ref(key: str) -> str:
        values = ledger.get(key)
        return f"{min(values):,} - {max(values):,} ({len(values)} runs)" if values else "not in the ledger"

    lines = [
        f"\ntokens per stage from Langfuse ({usage.traces} traces, {usage.rows_traced} of {rows_expected} rows traced)",
        f"  {'stage':<18} {'calls':>5} {'input':>8} {'output':>8} {'total':>8}   ledger totals for this stage",
    ]
    for stage, u in sorted(usage.per_stage.items()):
        lines.append(f"  {stage:<18} {u.calls:>5} {u.input:>8,} {u.output:>8,} {u.total:>8,}   {ref(stage)}")
    lines.append(f"  {'ALL':<18} {sum(u.calls for u in usage.per_stage.values()):>5} {sum(u.input for u in usage.per_stage.values()):>8,}"
                 f" {sum(u.output for u in usage.per_stage.values()):>8,} {usage.total:>8,}   whole runs in the ledger: {ref('ALL')}")
    if usage.rows_traced < rows_expected:
        lines.append(f"  WARNING: only {usage.rows_traced} of {rows_expected} rows have a trace; the numbers above are incomplete"
                     " (Langfuse still ingesting, or a worker runs without the Langfuse keys)")
    return lines


async def langfuse_section(project: dict[str, Any], *, environ: Any = os.environ, transport: httpx.AsyncBaseTransport | None = None,
                           wait: float = 90.0, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, ledger_path: Path = LEDGER_PATH) -> list[str]:
    """The report lines for --langfuse; never raises on Langfuse trouble (the smoke verdict does not depend on it)."""
    settings = langfuse_settings(environ)
    if settings is None:
        return ["\nLangfuse is not configured (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not both set): no token report."]
    public, secret, host = settings
    try:
        usage = await fetch_langfuse_usage(project["id"], host=host, public_key=public, secret_key=secret,
                                           expected_traces=len(project["rows"]), wait=wait, sleep=sleep, transport=transport)
    except (SmokeError, httpx.HTTPError, KeyError, ValueError) as error:
        return [f"\nLangfuse token report failed ({type(error).__name__}: {str(error)[:200]}); host {host}."]
    return usage_report(usage, load_ledger(ledger_path), len(project["rows"]))
