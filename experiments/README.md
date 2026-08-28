# Baseline experiment (config A)

Runs `dataset.json` (100 startup ideas, 10 of them flagged for a variance
subset) through the live system in pipeline mode and collects the full
generated output plus LLM cost/latency metrics from Langfuse, for later
comparison against agentic generation configs.

This is a research tool, not part of the product: nothing under
`bizstruct_ml` imports from here, and the Docker image build
(`bizstruct-ml/Dockerfile`) only ever `COPY`s `pyproject.toml` and `src/`,
so this directory never ships in the worker image.

## How it talks to the system

- `POST /api/generation` to start a project, then polls
  `GET /api/projects/{id}` every `--poll-interval` seconds until it hits a
  terminal `status` (`completed` or `failed`) or `--project-timeout` runs
  out. Both endpoints are currently unauthenticated in bizstruct-be (see
  `app/main.py` — only `/api/internal/*` requires `X-API-Key`); if that
  changes, set `EXPERIMENT_BACKEND_API_KEY` and it'll be sent as `X-API-Key`.
- Deliberately **not** Web PubSub — this is a one-shot script, polling is
  simpler and sufficient.
- No cross-cutting id needs to be invented for matching runs to Langfuse
  traces: `bizstruct_ml.observability.tracing.trace_block_generation()`
  already sets `session_id=project_id` on every trace. `project_id` (which
  the script gets straight back from `POST /api/generation`) is all
  `export-metrics` needs.

## Setup

Run everything from the `bizstruct-ml` directory, using its own venv (this
tooling deliberately adds no new dependencies — `httpx`, `pydantic`,
`langfuse`, `tenacity` are already in `pyproject.toml`):

```bash
cd bizstruct-ml
uv sync --extra dev
```

Required environment variables (no localhost fallback — the script raises
immediately if these are missing):

| Variable | Required for | Notes |
|---|---|---|
| `EXPERIMENT_BACKEND_BASE_URL` | all run modes | e.g. `http://localhost:8000` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | `export-metrics`, pilot's cost projection | |
| `LANGFUSE_HOST` | optional | defaults to `https://cloud.langfuse.com` |
| `EXPERIMENT_BACKEND_API_KEY` | optional | only if the public API ever gets an auth requirement |

Prices (`--input-price-per-1k` / `--output-price-per-1k`, or
`EXPERIMENT_INPUT_PRICE_PER_1K` / `EXPERIMENT_OUTPUT_PRICE_PER_1K`) are not
hardcoded anywhere — pass them explicitly whenever you want a cost figure.

## Order of operations

1. **Pilot first, always.** Runs a small slice (default 5 ideas), then
   exports Langfuse metrics for just that slice and prints a projected cost
   and time for the full 140-generation run:

   ```bash
   uv run python -m experiments.cli pilot \
     --input-price-per-1k 2.5 --output-price-per-1k 10
   ```

2. **Main coverage run** — all 100 ideas once each:

   ```bash
   uv run python -m experiments.cli main
   ```

3. **Variance run** — the 10 `variance_subset` ideas, 4 more times each
   (5 total per idea, matching the brief's "1 + 4 more"):

   ```bash
   uv run python -m experiments.cli variance
   ```

   `main` and `variance` are independent and restartable separately, as
   specified — you can run either one, interrupt it, and resume, without
   touching the other.

4. **Export Langfuse metrics** (repeatable, idempotent — safe to rerun if
   Langfuse's batcher hadn't caught up yet):

   ```bash
   uv run python -m experiments.cli export-metrics
   ```

   Prints a list of projects with fewer than expected block traces in
   Langfuse (previously observed under batch load without a forced flush —
   see the module docstring in `langfuse_export.py`).

5. **Regenerate the report** at any point:

   ```bash
   uv run python -m experiments.cli report \
     --input-price-per-1k 2.5 --output-price-per-1k 10
   ```

All four run/export modes accept `--dataset` and `--out-dir` (default
`results/{configuration}__{deployment}/` — see "Results directory
namespacing" below), `--concurrency` (default 5), `--project-timeout`
(default 1200s — see "Observed timing" below for why), `--poll-interval`
(default 5s).

## Resuming after an interruption

Every finished (idea, run_index) is appended to `results/runs.jsonl`
immediately (one JSON object per line, `fsync`ed on write). On restart, any
mode reads that file first and skips work already recorded there — killing
the process mid-run loses at most the in-flight batch, never anything
already completed.

## Throttling / 429s

Both the create and poll requests retry with exponential backoff (with
jitter) on HTTP 429 and 5xx and on network errors — the whole run never
aborts because of a single throttled or flaky request. A project that never
recovers within `--project-timeout` is recorded with `status: timeout`, not
treated as a crash.

## Observed timing (from a live 5-idea pilot — read before trusting the brief's ~60s/pass figure)

A real pilot against the running stack (Aug 27, `gpt-5.6-sol`, concurrency 5)
showed each **LLM call** taking 13-56s — consistent with the brief. But the
**gap between one block's hook completing and the next block's queue
message being picked up** was consistently 60-200s (one project saw a 206s
gap between `what_if` and `hypotheses`). That dispatch latency, not LLM
inference, dominates wall-clock time: a full 8-block project took ~900s
(15 min) end to end in this environment, not ~60s. 4 of 5 pilot projects
didn't finish within the old 600s default timeout as a direct result —
hence the 1200s default above. If you see the same pattern, budget
accordingly rather than assuming the brief's per-pass estimate holds for
wall-clock planning.

Separately, the pilot surfaced a real backend bug worth knowing about
before a big run: `POST /api/internal/hook` 500'd once with
`asyncpg.exceptions.UntranslatableCharacterError: \u0000 cannot be
converted to text` — the LLM occasionally emits a NUL byte, which Postgres'
`text` columns reject. bizstruct-ml treats a 5xx hook response as
transient and abandons+redelivers the message, so this self-heals on
retry (the block regenerates and succeeds) but costs several extra minutes
per occurrence. Not something this script works around — flagging it here
since it affects timing and is out of scope to fix from this directory
(see the brief's constraints: no changes to bizstruct-be/bizstruct-ml).

## Output files (in `--out-dir`, default `results/{configuration}__{deployment}/`)

- **`run_meta.json`** — the conditions this run was produced under: git
  SHAs of all four repos (+ dirty flags), dataset hash, domain version,
  deployment/model_version/guardrails (pulled from the Azure control plane
  via `az`, see below), concurrency/timeout/poll settings, actual worker
  replica count, started/finished timestamps. No secrets — only hosts and
  names. Any field that couldn't be determined is `null`, with the reason
  recorded in `meta_warnings` rather than silently dropped.
- **`runs.jsonl`** — one line per (idea, run_index): identification,
  outcome, duration, and the full generated content of every block exactly
  as the backend returned it.
- **`metrics.csv`** — one row per (project, block): `input_tokens`,
  `output_tokens`, `latency_ms`, `retries`, sourced from Langfuse.
- **`summary.md`** — run conditions (from `run_meta.json`) followed by
  outcome counts, average duration, token/retry totals, cost estimate (if
  prices were given), and a breakdown by `expected_pattern`,
  `detail_level`, `market_type`, `industry`.

## Results directory namespacing (comparing configurations/models)

`--out-dir` defaults to `results/{configuration}__{deployment}/` — e.g.
`results/A_pipeline__gpt-5.6-sol/`. `--configuration` defaults to
`A_pipeline`; pass a different label once B/C/D architectures exist.
Resume (see above) is scoped to one such directory, so rerunning the same
ideas under a different model or configuration never gets skipped as
"already done". Pass `--out-dir` explicitly to override the default
entirely. The original flat `results/` from the first baseline pilot is
left untouched — it predates this namespacing and stays as historical data.

## Switching the Azure OpenAI deployment for a run

`bizstruct_ml.config.Settings` reads `AZURE_OPENAI_DEPLOYMENT` once at
process start (pydantic-settings, no runtime override hook) — so the only
way to run a given batch against a different deployment is to change the
container's environment and restart it. `--deployment <name>` on any run
subcommand does this automatically (`experiments/deploy.py`):
rewrites `AZURE_OPENAI_DEPLOYMENT` (and `--api-version` if given) in
`bizstruct-ml/.env`, then runs `docker compose up -d --force-recreate ml`
and blocks until the container's Service Bus consumer logs
`consumer_ready`. **`docker restart` does not reload `env_file` — only
`--force-recreate` does; this bit us once already (see git history) and
`deploy.py` never uses `restart`.** `.env` is rewritten by parsing it into
lines and reserializing, not via shell `>>`, which previously corrupted a
line lacking a trailing newline.

If `--deployment` isn't given, whatever `bizstruct-ml/.env` currently has
is used (and read for `run_meta.json`/the out-dir name) — no switch happens.

To create a new deployment (fixed model version, no auto-upgrade, matching
how `gpt-5.6-sol` itself is configured):

```bash
az cognitiveservices account deployment show \
  -n <account> -g <resource-group> --deployment-name gpt-5.6-sol
# copy model.version, then:
az rest --method put \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/deployments/<new-deployment-name>?api-version=2026-05-01" \
  --body '{"sku":{"name":"GlobalStandard","capacity":50},"properties":{"model":{"format":"OpenAI","name":"<new-deployment-name>","version":"<version>"},"versionUpgradeOption":"NoAutoUpgrade"}}'
```
(`az cognitiveservices account deployment create` has no
`--version-upgrade-option` flag in this CLI version — `az rest` against the
ARM API is the only way to set it at creation time. Check quota first with
`az cognitiveservices usage list --location <region>`.)

## Comparative model runs

```bash
uv run python -m experiments.cli pilot --deployment gpt-5.6-terra --configuration A_pipeline --pilot-n 5 \
  --azure-resource-group <rg> --azure-account-name <account>
```

`--pilot-n 5` with the dataset's natural ordering always picks idea-001
through idea-005 — the "same 5 ideas across every model" the comparative
brief calls for. Repeat per candidate deployment (including a fresh
`gpt-5.6-sol` run — don't reuse the original baseline pilot's numbers,
they predate the NUL-byte hook-500 fix and used a different timeout).

Then build the comparison table:

```bash
uv run python -m experiments.cli compare \
  --results-dir experiments/results/A_pipeline__gpt-5.6-sol \
  --results-dir experiments/results/A_pipeline__gpt-5.6-terra \
  --results-dir experiments/results/A_pipeline__gpt-5.4-mini \
  --results-dir experiments/results/A_pipeline__gpt-5.4-nano \
  --input-price-per-1k <price> --output-price-per-1k <price>
```

`compare` reads each directory's `run_meta.json` + `runs.jsonl` +
`metrics.csv` and writes one row per results dir: completed/failed/timeout
counts, avg duration, tokens, total retries, avg retries/block, avg
latency, and cost if prices are given (uniform across all rows — pass
per-model prices by running `compare` separately per pair if they differ).

### min_length provocation test (per model)

```bash
uv run python -m experiments.cli min-length-probe --deployment <name>
```

Hits the Azure OpenAI API directly (not through the worker/queue at all —
works regardless of which deployment the container is currently running),
with a schema requiring `message: str` of at least 40 characters while the
system prompt demands the single word "ok". Appends one JSON line to
`results/min_length_probe.jsonl` recording the `outcome`
(`padded_to_satisfy_schema` / `instruction_followed_schema_violated` /
`api_error` / ...) and the actual text returned.

### Quality sample (side-by-side, no scoring)

```bash
uv run python -m experiments.cli quality-sample \
  --results-dir experiments/results/A_pipeline__gpt-5.6-sol \
  --results-dir experiments/results/A_pipeline__gpt-5.6-terra \
  --idea-id idea-001 --idea-id idea-002 --idea-id idea-003
```

Writes `experiments/quality_sample.md`: for each idea, each block's raw
generated JSON from each model's results dir, one after another. No
scoring or commentary — that's for a human reader, per the brief.

## Langfuse tags for configuration/model comparison (part A2 — limitation)

`deployment` is recoverable for free: `generation_span("llm_call", model=
llm.model_name, ...)` in `bizstruct_ml/generators/base.py` already puts it
on Langfuse's `providedModelName`/model fields for every GENERATION
observation, no worker change needed.

`configuration` and `run_id`, however, **cannot** be attached to Langfuse
traces without editing `bizstruct-ml`. `trace_block_generation()`'s
`propagate_attributes(...)` call in `observability/tracing.py` is given a
hardcoded `metadata={"project_id", "block", "attempt_number",
"bizstruct_domain_version"}` and `tags=[block, mode]` (`mode` is always the
literal `"pipeline"`) — nothing from the queue message's `payload` field
(the only per-request lever this script has, via `POST /api/generation` →
`enqueue_block`) ever reaches that call. Per the brief's instruction, this
directory does not modify bizstruct-ml to add a hook for it. In practice
this doesn't block analysis: every run's `project_id`s are already recorded
in `run_meta.json`/`runs.jsonl` per results directory, so joining Langfuse
data back to a `(configuration, run_id)` by `project_id` works fine without
either being present in Langfuse itself — just not as a native Langfuse
filter/tag.
