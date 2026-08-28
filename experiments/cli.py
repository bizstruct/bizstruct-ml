"""CLI entrypoint for the baseline-experiment tooling.

Run from the bizstruct-ml directory (so bizstruct_ml's own deps —
httpx, pydantic, langfuse, tenacity, openai — are on the path):

    uv run python -m experiments.cli pilot
    uv run python -m experiments.cli main
    uv run python -m experiments.cli variance
    uv run python -m experiments.cli language-comparison --language uk
    uv run python -m experiments.cli language-comparison --language en
    uv run python -m experiments.cli calibration-set --version v1
    uv run python -m experiments.cli calibration-export --version v1
    uv run python -m experiments.cli calibration-degrade --action export --idea-id idea-001 --out /tmp/idea-001.json
    uv run python -m experiments.cli calibration-degrade --action import --idea-id idea-001 --in /tmp/idea-001.json --criterion K1
    uv run python -m experiments.cli calibration-input --action template --out /tmp/scores_template.csv
    uv run python -m experiments.cli calibration-input --action validate --in /tmp/scores_filled.csv
    uv run python -m experiments.cli calibration-report --version v1
    uv run python -m experiments.cli export-metrics
    uv run python -m experiments.cli report
    uv run python -m experiments.cli compare --results-dir ... --results-dir ...
    uv run python -m experiments.cli min-length-probe --deployment ...
    uv run python -m experiments.cli quality-sample --results-dir ... --idea-id ...

See README.md for the full walkthrough, including how model switching
(--deployment) and results-directory namespacing (--configuration) work.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path

from experiments.common import build_plan, load_dataset, load_existing_results, require_env
from experiments.report import estimate_cost, generate_compare, generate_report, load_metrics_totals
from experiments.runner import run_plan

TOTAL_PLANNED_RUNS = 140  # 100 coverage + 10 * 4 variance reruns, per the baseline experiment brief
REPO_ROOT = Path(__file__).resolve().parents[2]  # .../bizstruct/
ML_ROOT = Path(__file__).resolve().parents[1]  # .../bizstruct-ml/
DEFAULT_ML_ENV_FILE = ML_ROOT / ".env"


def _common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dataset", type=Path, default=Path(__file__).parent / "dataset.json")
    p.add_argument(
        "--out-dir", type=Path, default=None,
        help="Defaults to results/{configuration}__{deployment}/ — see README.md part A3.",
    )
    p.add_argument("--configuration", default=os.environ.get("EXPERIMENT_CONFIGURATION", "A_pipeline"),
                    help="Label for which architecture variant is running (A_pipeline/B_.../C_.../D_...).")
    p.add_argument("--deployment", default=os.environ.get("EXPERIMENT_DEPLOYMENT"),
                    help="Azure OpenAI deployment name to run against. If different from what "
                         f"{DEFAULT_ML_ENV_FILE} currently has, the ml container is switched to it "
                         "first (see deploy.py) — this restarts the container.")
    p.add_argument("--api-version", default=os.environ.get("EXPERIMENT_API_VERSION"),
                    help="Optional AZURE_OPENAI_API_VERSION override to pair with --deployment.")
    p.add_argument("--ml-env-file", type=Path, default=DEFAULT_ML_ENV_FILE)
    p.add_argument("--compose-dir", type=Path, default=REPO_ROOT)
    p.add_argument("--azure-resource-group", default=os.environ.get("EXPERIMENT_AZURE_RESOURCE_GROUP"),
                    help="For run_meta.json's model_version/guardrails lookup via `az`. Optional.")
    p.add_argument("--azure-account-name", default=os.environ.get("EXPERIMENT_AZURE_ACCOUNT_NAME"),
                    help="For run_meta.json's model_version/guardrails lookup via `az`. Optional.")
    p.add_argument("--concurrency", type=int, default=int(os.environ.get("EXPERIMENT_CONCURRENCY", 5)))
    p.add_argument(
        "--project-timeout",
        type=float,
        default=float(os.environ.get("EXPERIMENT_PROJECT_TIMEOUT", 1200)),
        help=(
            "Seconds before an unfinished project is recorded as 'timeout' (default 1200 = 20 min). "
            "Higher than the brief's ~60s/pass assumption: the live pilot showed inter-block queue "
            "dispatch latency (60-200s between one block's hook and the next block's message being "
            "picked up) dominating over LLM call time (13-56s) — see README.md 'Observed timing'."
        ),
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.environ.get("EXPERIMENT_POLL_INTERVAL", 5)),
        help="Seconds between GET /api/projects/{id} polls (default 5).",
    )
    p.add_argument("--input-price-per-1k", type=float, default=_env_float("EXPERIMENT_INPUT_PRICE_PER_1K"))
    p.add_argument("--output-price-per-1k", type=float, default=_env_float("EXPERIMENT_OUTPUT_PRICE_PER_1K"))


def _env_float(name: str) -> float | None:
    v = os.environ.get(name)
    return float(v) if v else None


def _backend_client_args() -> tuple[str, str | None]:
    base_url = require_env("EXPERIMENT_BACKEND_BASE_URL")
    api_key = os.environ.get("EXPERIMENT_BACKEND_API_KEY")  # optional — see http.py docstring
    return base_url, api_key


def _langfuse_client():
    from langfuse import Langfuse

    public_key = require_env("LANGFUSE_PUBLIC_KEY")
    secret_key = require_env("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def _export(client, records, csv_path):
    from experiments.langfuse_export import export_metrics

    return export_metrics(client, records, csv_path)


def _print_incomplete(incomplete) -> None:
    if not incomplete:
        print("[export] all projects have complete Langfuse data")
        return
    print(f"[export] {len(incomplete)} project(s) with incomplete Langfuse data:")
    for record, found, expected in incomplete:
        print(
            f"  - {record.idea_id} run{record.run_index} project_id={record.project_id}: "
            f"{found}/{expected} block traces found"
        )


def _resolve_deployment(args) -> str:
    """Ensures the ml container is running the requested deployment,
    switching it (and blocking until ready) if needed. Returns the
    deployment name actually in effect, for out-dir naming and run_meta."""
    from experiments.deploy import DeploySwitchError, get_env_value, switch_deployment
    from experiments.run_meta import read_ml_env

    current = get_env_value(args.ml_env_file, "AZURE_OPENAI_DEPLOYMENT")
    target = args.deployment or current
    if not target:
        raise SystemExit(
            f"No --deployment given and AZURE_OPENAI_DEPLOYMENT not found in {args.ml_env_file}"
        )

    if args.deployment and args.deployment != current:
        print(f"[deploy] switching ml container from deployment={current!r} to {args.deployment!r}...")
        try:
            switch_deployment(
                env_path=args.ml_env_file,
                compose_project_dir=args.compose_dir,
                deployment=args.deployment,
                api_version=args.api_version,
            )
        except DeploySwitchError as e:
            raise SystemExit(f"[deploy] failed: {e}") from None
        print(f"[deploy] ml container now running deployment={args.deployment!r}")

    return target


def _default_out_dir(args, deployment: str, language: str | None = None) -> Path:
    safe_deployment = deployment.replace("/", "_")
    name = f"{args.configuration}__{safe_deployment}"
    if language:
        name += f"__{language}"
    return Path(__file__).parent / "results" / name


def cmd_run(args, mode: str, language: str | None = None) -> None:
    from experiments.run_meta import build_run_meta, finalize_run_meta, read_ml_env, write_run_meta

    deployment = _resolve_deployment(args)
    out_dir = args.out_dir or _default_out_dir(args, deployment, language)
    out_dir.mkdir(parents=True, exist_ok=True)

    ideas = load_dataset(args.dataset)
    plan_mode = "main" if mode == "pilot" else mode
    tasks = build_plan(ideas, plan_mode, language=language or "en")
    if mode == "pilot":
        tasks = tasks[: args.pilot_n]
        print(f"[pilot] running {len(tasks)} ideas: {', '.join(t.idea.id for t in tasks)}")
    if mode == "language_comparison":
        print(f"[language-comparison] running {len(tasks)} variance_subset ideas at language={language!r}")

    run_meta = build_run_meta(
        run_id=f"{args.configuration}__{deployment}__{mode}__{int(time.time())}",
        configuration=args.configuration,
        mode=mode,
        dataset_path=args.dataset,
        concurrency=args.concurrency,
        project_timeout=args.project_timeout,
        poll_interval=args.poll_interval,
        ml_env=read_ml_env(args.ml_env_file),
        azure_resource_group=args.azure_resource_group,
        azure_account_name=args.azure_account_name,
        language=language,
    )
    write_run_meta(run_meta, out_dir)
    for w in run_meta.meta_warnings:
        print(f"[run_meta] warning: {w}")

    runs_path = out_dir / "runs.jsonl"
    base_url, api_key = _backend_client_args()

    start = time.monotonic()
    asyncio.run(
        run_plan(
            tasks,
            backend_base_url=base_url,
            backend_api_key=api_key,
            runs_path=runs_path,
            concurrency=args.concurrency,
            poll_interval=args.poll_interval,
            project_timeout=args.project_timeout,
        )
    )
    wall_seconds = time.monotonic() - start
    finalize_run_meta(out_dir)
    print(f"[{mode}] wall-clock time: {wall_seconds:.0f}s ({wall_seconds / 60:.1f} min)")
    print(f"[{mode}] results dir: {out_dir}")

    if mode == "pilot":
        _pilot_cost_projection(args, out_dir, wall_seconds, len(tasks))


def _pilot_cost_projection(args, out_dir: Path, wall_seconds: float, n_ran: int) -> None:
    print("[pilot] waiting for Langfuse to flush, then exporting metrics for cost projection...")
    print("        (Langfuse's batcher can lag a few seconds behind live traffic; rerun "
          "'export-metrics' later if this looks incomplete)")
    time.sleep(15)

    try:
        client = _langfuse_client()
    except SystemExit as e:
        print(f"[pilot] skipping cost projection — {e}")
        return

    records = list(load_existing_results(out_dir / "runs.jsonl").values())
    incomplete = _export(client, records, out_dir / "metrics.csv")
    _print_incomplete(incomplete)

    totals = load_metrics_totals(out_dir / "metrics.csv")
    print(
        f"[pilot] measured over {n_ran} project(s): "
        f"{totals.input_tokens:,} input tokens, {totals.output_tokens:,} output tokens, "
        f"{totals.total_retries} total retries"
    )

    generate_report(
        out_dir / "runs.jsonl",
        out_dir / "metrics.csv",
        out_dir / "summary.md",
        input_price_per_1k=args.input_price_per_1k,
        output_price_per_1k=args.output_price_per_1k,
    )

    if args.input_price_per_1k is None or args.output_price_per_1k is None:
        print("[pilot] no --input-price-per-1k/--output-price-per-1k given — skipping cost projection")
        return

    if n_ran == 0:
        return

    avg_input = totals.input_tokens / n_ran
    avg_output = totals.output_tokens / n_ran
    avg_wall = wall_seconds / n_ran

    full_input = avg_input * TOTAL_PLANNED_RUNS
    full_output = avg_output * TOTAL_PLANNED_RUNS
    full_cost = estimate_cost(full_input, full_output, args.input_price_per_1k, args.output_price_per_1k)
    full_wall_serial = avg_wall * TOTAL_PLANNED_RUNS

    print("")
    print(f"[pilot] projected full run ({TOTAL_PLANNED_RUNS} generations):")
    print(f"  - tokens: ~{full_input:,.0f} input, ~{full_output:,.0f} output")
    print(f"  - cost:   ~${full_cost:,.2f}")
    print(
        f"  - time (serial-equivalent): ~{full_wall_serial / 3600:.1f}h — "
        f"divide roughly by --concurrency for the wall-clock estimate at that parallelism"
    )


CALIBRATION_ROOT = Path(__file__).parent / "calibration" / "sets"


def _calibration_set_dir(version: str) -> Path:
    return CALIBRATION_ROOT / version


def cmd_calibration_set(args) -> None:
    """Generates the 5-project rubric-calibration set (part A of the
    calibration brief) — pipeline mode, English, on the given --deployment
    (gpt-5.6-terra for the real calibration run). Reuses the same run_meta/
    runner machinery as main/pilot/variance/language-comparison; the only
    difference is the fixed 5-idea plan (build_plan's 'calibration' mode)
    and the out-dir, which is the versioned calibration/sets/<version>/
    directory rather than results/ — kept separate so a later rubric
    change can't accidentally overwrite the artifact it needs to be
    compared against."""
    from experiments.run_meta import build_run_meta, finalize_run_meta, read_ml_env, write_run_meta

    deployment = _resolve_deployment(args)
    out_dir = _calibration_set_dir(args.version)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.overwrite:
        raise SystemExit(
            f"{out_dir} already exists and is non-empty — calibration sets are versioned artifacts, "
            f"not meant to be silently overwritten. Pass a new --version or --overwrite to replace it."
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    ideas = load_dataset(args.dataset)
    tasks = build_plan(ideas, "calibration", language="en")
    idea_ids = [t.idea.id for t in tasks]
    print(f"[calibration-set] version={args.version!r} running {len(tasks)} ideas: {', '.join(idea_ids)}")

    run_meta = build_run_meta(
        run_id=f"calibration__{deployment}__{args.version}__{int(time.time())}",
        configuration="calibration",
        mode="calibration",
        dataset_path=args.dataset,
        concurrency=args.concurrency,
        project_timeout=args.project_timeout,
        poll_interval=args.poll_interval,
        ml_env=read_ml_env(args.ml_env_file),
        azure_resource_group=args.azure_resource_group,
        azure_account_name=args.azure_account_name,
        language="en",
    )
    write_run_meta(run_meta, out_dir)
    for w in run_meta.meta_warnings:
        print(f"[run_meta] warning: {w}")

    # Explicit record of exactly which 5 ideas this version pins — the
    # brief asks this be fixed, and runs.jsonl alone requires parsing to
    # recover it.
    import json as _json
    (out_dir / "idea_ids.json").write_text(_json.dumps({"idea_ids": idea_ids}, indent=2), encoding="utf-8")

    runs_path = out_dir / "runs.jsonl"
    base_url, api_key = _backend_client_args()

    start = time.monotonic()
    asyncio.run(
        run_plan(
            tasks,
            backend_base_url=base_url,
            backend_api_key=api_key,
            runs_path=runs_path,
            concurrency=args.concurrency,
            poll_interval=args.poll_interval,
            project_timeout=args.project_timeout,
        )
    )
    wall_seconds = time.monotonic() - start
    finalize_run_meta(out_dir)
    print(f"[calibration-set] wall-clock time: {wall_seconds:.0f}s ({wall_seconds / 60:.1f} min)")
    print(f"[calibration-set] set dir: {out_dir}")

    print("[calibration-set] waiting for Langfuse to flush, then exporting metrics for cost visibility...")
    time.sleep(15)
    try:
        client = _langfuse_client()
        records = list(load_existing_results(runs_path).values())
        incomplete = _export(client, records, out_dir / "metrics.csv")
        _print_incomplete(incomplete)
        generate_report(
            runs_path, out_dir / "metrics.csv", out_dir / "summary.md",
            input_price_per_1k=args.input_price_per_1k, output_price_per_1k=args.output_price_per_1k,
        )
        totals = load_metrics_totals(out_dir / "metrics.csv")
        print(f"[calibration-set] {totals.input_tokens:,} input tokens, {totals.output_tokens:,} output tokens")
        if args.input_price_per_1k is not None and args.output_price_per_1k is not None:
            cost = estimate_cost(totals.input_tokens, totals.output_tokens, args.input_price_per_1k, args.output_price_per_1k)
            print(f"[calibration-set] cost: ~${cost:,.4f}")
    except SystemExit as e:
        print(f"[calibration-set] skipping cost export — {e}")


def cmd_calibration_export(args) -> None:
    from experiments.calibration.export import build_calibration_export

    set_dir = _calibration_set_dir(args.version)
    out_dir = set_dir / "export"
    keys_dir = set_dir / "keys"
    ideas = load_dataset(args.dataset)
    idea_texts = {i.id: i.text for i in ideas}

    exported = build_calibration_export(set_dir, out_dir, keys_dir, idea_texts, seed=args.seed)
    for e in exported:
        flag = " [degraded]" if e.degraded else ""
        print(f"[calibration-export] {e.file_id} <- {e.idea_id}{flag}, ~{e.tokens_estimated} tokens")
    print(f"[calibration-export] wrote {len(exported)} files to {out_dir}")
    print(f"[calibration-export] key + token counts: {keys_dir}")


def cmd_calibration_degrade(args) -> None:
    from experiments.calibration.degrade import export_for_editing, import_edited

    set_dir = _calibration_set_dir(args.version)
    if args.action == "export":
        if args.out is None:
            raise SystemExit("--out is required for --action export")
        export_for_editing(set_dir, args.idea_id, args.out)
        print(f"[calibration-degrade] wrote {args.out} — edit it by hand, then run 'calibration-degrade import'")
    elif args.action == "import":
        if args.in_path is None or args.criterion is None:
            raise SystemExit("--in and --criterion are required for --action import")
        result = import_edited(set_dir, args.idea_id, args.in_path, args.criterion, note=args.note or "")
        if result.ok:
            print(f"[calibration-degrade] structure OK — degraded/{args.idea_id}.json written, manifest updated")
        else:
            print("[calibration-degrade] structural check FAILED — nothing written:")
            for err in result.errors:
                print(f"  - {err}")
            raise SystemExit(1)


def cmd_calibration_input(args) -> None:
    from experiments.calibration.export import FILE_LETTERS
    from experiments.calibration.scoring import store_scores, validate_scores, write_score_template

    file_ids = [f"project-{letter}" for letter in FILE_LETTERS]

    if args.action == "template":
        if args.out is None:
            raise SystemExit("--out is required for --action template")
        write_score_template(args.out, file_ids)
        print(f"[calibration-input] wrote template ({len(file_ids)} files x 3 rounds x 5 criteria) to {args.out}")
        return

    # action == "validate"
    if args.in_path is None:
        raise SystemExit("--in is required for --action validate")
    set_dir = _calibration_set_dir(args.version)
    result = validate_scores(args.in_path, file_ids)
    if not result.ok:
        print("[calibration-input] validation FAILED — nothing stored:")
        for err in result.errors:
            print(f"  - {err}")
        raise SystemExit(1)
    stored_path = store_scores(set_dir, result.rows)
    print(f"[calibration-input] {len(result.rows)} rows valid, stored at {stored_path}")


def cmd_calibration_report(args) -> None:
    from experiments.calibration.scoring import build_calibration_report

    set_dir = _calibration_set_dir(args.version)
    keys_dir = set_dir / "keys"
    out_path = args.out or (set_dir / "calibration_report.md")
    build_calibration_report(set_dir, keys_dir, out_path)
    print(f"[calibration-report] wrote {out_path}")


def cmd_export_metrics(args) -> None:
    deployment = args.deployment or _current_or_none(args)
    out_dir = args.out_dir or _default_out_dir(args, deployment)
    records = list(load_existing_results(out_dir / "runs.jsonl").values())
    client = _langfuse_client()
    incomplete = _export(client, records, out_dir / "metrics.csv")
    _print_incomplete(incomplete)


def _current_or_none(args) -> str:
    from experiments.deploy import get_env_value

    value = get_env_value(args.ml_env_file, "AZURE_OPENAI_DEPLOYMENT")
    if not value:
        raise SystemExit(
            "No --deployment given and AZURE_OPENAI_DEPLOYMENT not found in "
            f"{args.ml_env_file} — pass --deployment or --out-dir explicitly"
        )
    return value


def cmd_report(args) -> None:
    deployment = args.deployment or _current_or_none(args)
    out_dir = args.out_dir or _default_out_dir(args, deployment)
    generate_report(
        out_dir / "runs.jsonl",
        out_dir / "metrics.csv",
        out_dir / "summary.md",
        input_price_per_1k=args.input_price_per_1k,
        output_price_per_1k=args.output_price_per_1k,
    )


def cmd_compare(args) -> None:
    generate_compare(
        [Path(d) for d in args.results_dirs],
        Path(args.out),
        input_price_per_1k=args.input_price_per_1k,
        output_price_per_1k=args.output_price_per_1k,
    )


def cmd_min_length_probe(args) -> None:
    asyncio.run(_run_min_length_probe(args))


async def _run_min_length_probe(args) -> None:
    import json

    from experiments.min_length_probe import run_probe
    from experiments.run_meta import read_ml_env

    env = read_ml_env(args.ml_env_file)
    endpoint = args.endpoint or env.get("AZURE_OPENAI_ENDPOINT")
    api_key = args.api_key or env.get("AZURE_OPENAI_API_KEY")
    # Matches bizstruct_ml.config.Settings.azure_openai_api_version's own
    # default — .env doesn't set this explicitly and the worker still runs
    # fine against it, so the probe should behave the same way rather than
    # requiring a value the worker itself doesn't require.
    api_version = args.api_version or env.get("AZURE_OPENAI_API_VERSION") or "2024-10-21"
    if not endpoint or not api_key:
        raise SystemExit(
            "Missing endpoint/api-key — pass them explicitly or ensure "
            f"{args.ml_env_file} has AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_KEY"
        )
    result = await run_probe(endpoint=endpoint, api_key=api_key, api_version=api_version, deployment=args.deployment)
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


def cmd_quality_sample(args) -> None:
    from experiments.common import BLOCK_NAMES
    from experiments.quality_sample import build_quality_sample_md

    blocks = tuple(args.blocks) if args.blocks else BLOCK_NAMES
    md = build_quality_sample_md(
        [Path(d) for d in args.results_dirs], args.idea_ids, run_index=args.run_index, blocks=blocks
    )
    args.out.write_text(md, encoding="utf-8")
    print(f"[quality_sample] wrote {args.out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="BizStruct baseline-experiment runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pilot = sub.add_parser("pilot", help="Run a small N-idea slice, then project full-run cost/time")
    _common_args(p_pilot)
    p_pilot.add_argument("--pilot-n", type=int, default=5)
    p_pilot.set_defaults(func=lambda a: cmd_run(a, "pilot"))

    p_main = sub.add_parser("main", help="Run all 100 ideas once each (run_index=0)")
    _common_args(p_main)
    p_main.set_defaults(func=lambda a: cmd_run(a, "main"))

    p_variance = sub.add_parser("variance", help="Run the 10 variance_subset ideas 4 more times each")
    _common_args(p_variance)
    p_variance.set_defaults(func=lambda a: cmd_run(a, "variance"))

    p_language = sub.add_parser(
        "language-comparison",
        help="Run the 10 variance_subset ideas once each at a given --language "
             "(part F of the data-quality-fixes brief). Run twice, once per "
             "language, into results/{configuration}__{deployment}__{language}/.",
    )
    _common_args(p_language)
    p_language.add_argument("--language", required=True, choices=["uk", "en"])
    p_language.set_defaults(func=lambda a: cmd_run(a, "language_comparison", language=a.language))

    p_export = sub.add_parser("export-metrics", help="Pull token/latency/retry metrics from Langfuse into metrics.csv")
    _common_args(p_export)
    p_export.set_defaults(func=cmd_export_metrics)

    # ── rubric calibration (manual evaluation) ──────────────────────────
    p_cal_set = sub.add_parser(
        "calibration-set",
        help="Generate the 5-project rubric-calibration set (pipeline, English, "
             "into calibration/sets/<version>/ — a versioned artifact).",
    )
    _common_args(p_cal_set)
    p_cal_set.add_argument("--version", default="v1", help="Names the set directory; bump this for a fresh set.")
    p_cal_set.add_argument("--overwrite", action="store_true", help="Allow overwriting a non-empty existing version.")
    p_cal_set.set_defaults(func=cmd_calibration_set)

    p_cal_export = sub.add_parser(
        "calibration-export",
        help="Build the 5 self-contained project-A.md..project-E.md judge files "
             "from a calibration set, plus the (separate) key/token-count files.",
    )
    p_cal_export.add_argument("--version", default="v1")
    p_cal_export.add_argument("--dataset", type=Path, default=Path(__file__).parent / "dataset.json")
    p_cal_export.add_argument("--seed", type=int, default=None, help="Optional fixed seed for the file-letter/criteria-order shuffle.")
    p_cal_export.set_defaults(func=cmd_calibration_export)

    p_cal_degrade = sub.add_parser(
        "calibration-degrade",
        help="Export one calibration-set project for hand-editing, or import an "
             "edited file back with a structural check (part C).",
    )
    p_cal_degrade.add_argument("--version", default="v1")
    p_cal_degrade.add_argument("--action", choices=["export", "import"], required=True)
    p_cal_degrade.add_argument("--idea-id", required=True)
    p_cal_degrade.add_argument("--out", type=Path, help="Where to write the editable file (export).")
    p_cal_degrade.add_argument("--in", dest="in_path", type=Path, help="The hand-edited file to import (import).")
    p_cal_degrade.add_argument("--criterion", choices=["K1", "K2"], help="Which criterion this degrades (import).")
    p_cal_degrade.add_argument("--note", default="", help="Free-text note for the manifest (import).")
    p_cal_degrade.set_defaults(func=cmd_calibration_degrade)

    p_cal_input = sub.add_parser(
        "calibration-input",
        help="Write a blank scores template, or validate+store a filled-in one (part D).",
    )
    p_cal_input.add_argument("--version", default="v1")
    p_cal_input.add_argument("--action", choices=["template", "validate"], required=True)
    p_cal_input.add_argument("--out", type=Path, help="Where to write the template (template).")
    p_cal_input.add_argument("--in", dest="in_path", type=Path, help="The filled-in scores CSV (validate).")
    p_cal_input.set_defaults(func=cmd_calibration_input)

    p_cal_report = sub.add_parser(
        "calibration-report",
        help="Build calibration_report.md from stored scores + the key/degraded-manifest files.",
    )
    p_cal_report.add_argument("--version", default="v1")
    p_cal_report.add_argument("--out", type=Path, default=None)
    p_cal_report.set_defaults(func=cmd_calibration_report)

    p_report = sub.add_parser("report", help="Regenerate summary.md from runs.jsonl + metrics.csv + run_meta.json")
    _common_args(p_report)
    p_report.set_defaults(func=cmd_report)

    p_compare = sub.add_parser("compare", help="Build a cross-run comparison table from multiple results dirs")
    p_compare.add_argument("--results-dir", action="append", required=True, dest="results_dirs")
    p_compare.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "compare.md")
    p_compare.add_argument("--input-price-per-1k", type=float, default=_env_float("EXPERIMENT_INPUT_PRICE_PER_1K"))
    p_compare.add_argument("--output-price-per-1k", type=float, default=_env_float("EXPERIMENT_OUTPUT_PRICE_PER_1K"))
    p_compare.set_defaults(func=cmd_compare)

    p_probe = sub.add_parser("min-length-probe", help="Run the min_length provocation test (part B4) against one deployment")
    p_probe.add_argument("--deployment", required=True)
    p_probe.add_argument("--endpoint", default=None)
    p_probe.add_argument("--api-key", default=None)
    p_probe.add_argument("--api-version", default=None)
    p_probe.add_argument("--ml-env-file", type=Path, default=DEFAULT_ML_ENV_FILE)
    p_probe.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "min_length_probe.jsonl")
    p_probe.set_defaults(func=cmd_min_length_probe)

    p_quality = sub.add_parser("quality-sample", help="Build quality_sample.md side-by-side across model results dirs")
    p_quality.add_argument("--results-dir", action="append", required=True, dest="results_dirs")
    p_quality.add_argument("--idea-id", action="append", required=True, dest="idea_ids")
    p_quality.add_argument("--run-index", type=int, default=0)
    p_quality.add_argument(
        "--block", action="append", dest="blocks", default=None,
        help="Restrict to specific blocks (repeatable); default is all 8. "
             "E.g. --block architecture --block hypotheses for language_quality_sample.md (part F).",
    )
    p_quality.add_argument("--out", type=Path, default=Path(__file__).parent / "quality_sample.md")
    p_quality.set_defaults(func=cmd_quality_sample)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
