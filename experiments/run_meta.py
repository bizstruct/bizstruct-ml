"""run_meta.json: the conditions an experiment was produced under, so its results stay interpretable later.

Everything is read from OUTSIDE the worker: the sibling git checkouts, the installed bizstruct-domain, uv.lock, docker,
`az` and the environment variables of the current shell. The worker's `.env` files are never read. The prompt versions
are read by PARSING the `PROMPT_VERSION = "..."` constants of `src/bizstruct_ml/llm/prompts/*.py` (ast, no import):
this module imports no ml worker code. Only hosts and names are recorded, never keys or connection strings; the secret
guard runs over the file before it is written. A value that cannot be determined is null with the reason in
`meta_warnings`, never silently omitted.

A resumed run (same output directory) leaves the first meta in place and appends the new one to `resumes`; the report
warns when a recorded SHA, dirty flag, version or deployment differs (`incomparable`, in report.py)."""

import ast
import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import bizstruct_domain

from experiments.guard import write_guarded
from experiments.report import incomparable

ML_ROOT = Path(__file__).resolve().parent.parent
REPOS_ROOT = ML_ROOT.parent  # .../bizstruct/, where the sibling checkouts live
SIBLING_REPOS = ("bizstruct-domain", "bizstruct-be", "bizstruct-ml", "bizstruct-fe")
DEFAULT_COMPOSE_PROJECT = "bizstruct-stack"
SECRET_FLAG = re.compile(r"(password|key|token|secret)", re.I)
NOT_SECRET_FLAGS = {"--max-tokens"}  # a budget, not a credential

Cmd = Callable[[list[str]], str]  # runs a command and returns its stdout; raises on failure


def default_cmd(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30, check=True).stdout


def redact_command(argv: list[str]) -> list[str]:
    """The command line with the value of every key/password/token/secret option replaced."""
    redacted: list[str] = []
    hide_next = False
    for arg in argv:
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
        elif arg.startswith("--") and "=" in arg and arg.split("=", 1)[0] not in NOT_SECRET_FLAGS and SECRET_FLAG.search(arg.split("=", 1)[0]):
            redacted.append(arg.split("=", 1)[0] + "=<redacted>")
        elif arg.startswith("--") and arg not in NOT_SECRET_FLAGS and SECRET_FLAG.search(arg):
            redacted.append(arg)
            hide_next = True
        else:
            redacted.append(arg)
    return redacted


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: str, repos_root: Path, cmd: Cmd, warnings: list[str]) -> dict[str, Any] | None:
    path = repos_root / repo
    if not path.is_dir():
        warnings.append(f"git.{repo}: no checkout at {path}")
        return None
    try:
        head = cmd(["git", "-C", str(path), "rev-parse", "HEAD"]).strip()
        branch = cmd(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        dirty = bool(cmd(["git", "-C", str(path), "status", "--porcelain"]).strip())
    except Exception as error:  # noqa: BLE001 - any failure of the subprocess is a null plus a reason
        warnings.append(f"git.{repo}: {type(error).__name__}: {str(error)[:200]}")
        return None
    return {"head": head, "branch": branch, "dirty": dirty}


def prompt_versions(ml_root: Path, warnings: list[str]) -> dict[str, str | None]:
    """{prompt module: PROMPT_VERSION}, parsed from the source (swot and errc belong to the swot_errc_cycle stage)."""
    versions: dict[str, str | None] = {}
    directory = ml_root / "src" / "bizstruct_ml" / "llm" / "prompts"
    if not directory.is_dir():
        warnings.append(f"prompt_versions: {directory} not found")
        return versions
    for path in sorted(directory.glob("*.py")):
        if path.stem.startswith("_") or path.stem == "__init__":
            continue
        version = None
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROMPT_VERSION" for t in node.targets):
                version = ast.literal_eval(node.value)
        if version is None:
            warnings.append(f"prompt_versions.{path.stem}: no PROMPT_VERSION constant")
        versions[path.stem] = version
    return versions


def _host(url: str | None) -> str | None:
    parsed = urlparse(url) if url else None
    return parsed.hostname if parsed and parsed.hostname else None


def _model(role: str, deployment: str | None, endpoint: str | None, account: str | None, group: str | None,
           cmd: Cmd, warnings: list[str]) -> dict[str, Any]:
    info: dict[str, Any] = {"deployment": deployment, "endpoint_host": _host(endpoint), "model": None, "model_version": None}
    if not deployment:
        warnings.append(f"{role}.deployment: not set in the environment of this shell (the worker's .env is deliberately not read)")
        return info
    if not (account and group):
        warnings.append(f"{role}.model_version: --azure-account-name / --azure-resource-group not given, so `az` was not asked")
        return info
    try:
        data = json.loads(cmd(["az", "cognitiveservices", "account", "deployment", "show", "-n", account, "-g", group,
                               "--deployment-name", deployment, "-o", "json"]))
        model = data.get("properties", {}).get("model", {})
        info["model"], info["model_version"] = model.get("name"), model.get("version")
    except Exception as error:  # noqa: BLE001
        warnings.append(f"{role}.model_version: az failed ({type(error).__name__}: {str(error)[:200]})")
    return info


def _image(service: str, project: str, cmd: Cmd, warnings: list[str]) -> str | None:
    try:
        ids = cmd(["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}",
                   "--filter", f"label=com.docker.compose.service={service}"]).split()
        if not ids:
            warnings.append(f"docker.{service}_image_id: no running container of service {service!r} in compose project {project!r}")
            return None
        return cmd(["docker", "inspect", "--format", "{{.Image}}", ids[0]]).strip() or None
    except Exception as error:  # noqa: BLE001
        warnings.append(f"docker.{service}_image_id: docker unavailable ({type(error).__name__}: {str(error)[:200]})")
        return None


def identity_of(meta: Mapping[str, Any]) -> dict[str, Any]:
    """The fields that decide whether two runs are comparable (no time, command, sizes or branch names)."""
    return {
        "config": meta["config"],
        "ideas_sha256": meta["ideas"]["sha256"],
        "git": {repo: (None if info is None else {"head": info["head"], "dirty": info["dirty"]}) for repo, info in meta["git"].items()},
        "domain_version": meta["domain_version"],
        "uv_lock_sha256": meta["uv_lock_sha256"],
        "prompt_versions": meta["prompt_versions"],
        "docker": meta["docker"],
        "generator": {k: meta["generator"][k] for k in ("deployment", "model", "model_version")},
        "judge": {k: meta["judge"][k] for k in ("provider", "deployment", "model", "model_version")},
    }


def meta_ref_of(meta: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(identity_of(meta), sort_keys=True).encode()).hexdigest()


def collect_meta(
    *,
    command_line: list[str],
    config: str,
    ideas_path: Path,
    idea_count: int,
    repeats: int,
    concurrency: int,
    max_tokens: int | None,
    max_runs: int | None,
    enable_optional: list[str],
    environ: Mapping[str, str],
    compose_project: str = DEFAULT_COMPOSE_PROJECT,
    azure_account_name: str | None = None,
    azure_resource_group: str | None = None,
    judge_azure_account_name: str | None = None,
    cmd: Cmd = default_cmd,
    repos_root: Path = REPOS_ROOT,
    ml_root: Path = ML_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    lock = ml_root / "uv.lock"
    if lock.exists():
        lock_sha: str | None = _sha256(lock)
    else:
        lock_sha = None
        warnings.append(f"uv_lock_sha256: {lock} not found")
    meta: dict[str, Any] = {
        "schema": 1,
        "started_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "command": redact_command(command_line),
        "config": config,
        "ideas": {"path": str(ideas_path), "sha256": _sha256(ideas_path), "count": idea_count},
        "repeats": repeats, "concurrency": concurrency, "max_tokens": max_tokens, "max_runs": max_runs,
        "enable_optional": enable_optional,
        "git": {repo: _git(repo, repos_root, cmd, warnings) for repo in SIBLING_REPOS},
        "domain_version": getattr(bizstruct_domain, "__version__", None),
        "uv_lock_sha256": lock_sha,
        "prompt_versions": prompt_versions(ml_root, warnings),
        "docker": {
            "compose_project": compose_project,
            "api_image_id": _image("api", compose_project, cmd, warnings),
            "ml_image_id": _image("ml", compose_project, cmd, warnings),
        },
        "generator": _model("generator", environ.get("AZURE_OPENAI_DEPLOYMENT"), environ.get("AZURE_OPENAI_ENDPOINT"),
                            azure_account_name, azure_resource_group, cmd, warnings),
        "judge": {"provider": environ.get("JUDGE_PROVIDER"),
                  **_model("judge", environ.get("JUDGE_DEPLOYMENT"), environ.get("JUDGE_ENDPOINT"),
                           judge_azure_account_name or azure_account_name, azure_resource_group, cmd, warnings)},
    }
    if meta["domain_version"] is None:
        warnings.append("domain_version: bizstruct_domain has no __version__")
    if meta["judge"]["provider"] is None:
        warnings.append("judge.provider: JUDGE_PROVIDER not set in the environment of this shell")
    meta["meta_warnings"] = warnings
    meta["meta_ref"] = meta_ref_of(meta)
    return meta


def write_meta(out_dir: Path, meta: dict[str, Any], secrets: list[str]) -> tuple[Path, list[str]]:
    """Write run_meta.json (the secret guard runs first), or on a resume append to its `resumes` list.
    Returns the path and the warnings about runs that are no longer comparable with the first."""
    path = out_dir / "run_meta.json"
    if not path.exists():
        write_guarded(path, json.dumps({**meta, "resumes": []}, indent=2, ensure_ascii=False), secrets)
        return path, []
    existing = json.loads(path.read_text(encoding="utf-8"))
    warnings = incomparable(existing, meta)
    existing.setdefault("resumes", []).append(meta)
    write_guarded(path, json.dumps(existing, indent=2, ensure_ascii=False), secrets)
    return path, warnings
