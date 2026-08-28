"""Gathers and writes run_meta.json — the conditions a run was produced
under, so results are interpretable months later without guessing.

Everything here is read from outside bizstruct-ml (env vars, git, docker,
the Azure control plane via `az`) — nothing changes worker code. Any field
that can't be determined is written as null with the reason recorded in
meta_warnings, never silently omitted (see the experiment brief, part A1).

No secrets: only hosts/names are recorded, never keys or connection
strings (see _redact_endpoint / the deliberate omission of API keys below).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../bizstruct/
SIBLING_REPOS = ["bizstruct-domain", "bizstruct-be", "bizstruct-ml", "bizstruct-fe"]


class RunMeta(BaseModel):
    run_id: str
    configuration: str
    deployment: str | None = None
    model_version: str | None = None
    endpoint: str | None = None
    temperature: float | None = None
    generation_params: dict[str, Any] = Field(default_factory=dict)
    guardrails: str | None = None
    dataset_path: str
    dataset_sha256: str
    dataset_size: int
    domain_version: str | None = None
    git_commits: dict[str, str | None] = Field(default_factory=dict)
    git_dirty: dict[str, bool | None] = Field(default_factory=dict)
    concurrency: int
    project_timeout: float
    poll_interval: float
    worker_replicas: int | None = None
    started_at: str
    finished_at: str | None = None
    mode: str
    # Fixed condition for mode="language_comparison" runs (part F) — the
    # generation language ("uk"/"en") every task in this run was submitted
    # with. None for every other mode (language wasn't a controlled
    # variable before part E).
    language: str | None = None
    meta_warnings: list[str] = Field(default_factory=list)


def _sha256_and_size(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _git_info(repo_name: str, warnings: list[str]) -> tuple[str | None, bool | None]:
    repo_path = REPO_ROOT / repo_name
    if not repo_path.exists():
        warnings.append(f"git_commits.{repo_name}: repo path not found at {repo_path}")
        return None, None
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception as e:  # noqa: BLE001
        warnings.append(f"git_commits.{repo_name}: {e}")
        sha = None
    try:
        status = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        dirty = bool(status.strip())
    except Exception as e:  # noqa: BLE001
        warnings.append(f"git_dirty.{repo_name}: {e}")
        dirty = None
    return sha, dirty


def _domain_version(warnings: list[str]) -> str | None:
    try:
        import bizstruct_domain

        return bizstruct_domain.__version__
    except Exception as e:  # noqa: BLE001
        warnings.append(f"domain_version: could not import bizstruct_domain ({e})")
        return None


def _worker_replicas(name_prefix: str, warnings: list[str]) -> int | None:
    """Counts running containers by name prefix — a docker-compose-specific
    proxy for replica count. Documented as such: on KEDA/Azure Container
    Apps this wouldn't apply and would need the ACA API instead (not
    implemented — this deployment is docker-compose)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={name_prefix}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        names = [n for n in result.stdout.splitlines() if n.strip()]
        return len(names)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"worker_replicas: docker ps failed ({e}); is docker available here?")
        return None


def _redact_endpoint(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else None


def _azure_deployment_info(
    *, resource_group: str | None, account_name: str | None, deployment_name: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    """Best-effort query of the Azure control plane for facts the worker's
    own env/config can't provide (deployed model version, content-filter
    policy, auto-upgrade setting). Requires `az` logged in and
    resource_group/account_name — both optional CLI args since a run
    without Azure CLI access should still produce a run_meta.json, just
    with these fields null."""
    out: dict[str, Any] = {"model_version": None, "guardrails": None}
    if not (resource_group and account_name and deployment_name):
        warnings.append(
            "azure_deployment_info: --azure-resource-group/--azure-account-name not given, "
            "skipping model_version/guardrails lookup"
        )
        return out
    try:
        result = subprocess.run(
            [
                "az", "cognitiveservices", "account", "deployment", "show",
                "-n", account_name, "-g", resource_group,
                "--deployment-name", deployment_name, "-o", "json",
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(result.stdout)
        props = data.get("properties", {})
        out["model_version"] = props.get("model", {}).get("version")
        out["guardrails"] = props.get("raiPolicyName")
        out["version_upgrade_option"] = props.get("versionUpgradeOption")
        out["sku_capacity"] = data.get("sku", {}).get("capacity")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"azure_deployment_info: az cognitiveservices query failed ({e})")
    return out


def build_run_meta(
    *,
    run_id: str,
    configuration: str,
    mode: str,
    dataset_path: Path,
    concurrency: int,
    project_timeout: float,
    poll_interval: float,
    ml_env: dict[str, str],
    azure_resource_group: str | None,
    azure_account_name: str | None,
    docker_name_prefix: str = "bizstruct_ml",
    language: str | None = None,
) -> RunMeta:
    warnings: list[str] = []

    dataset_sha256, dataset_size = _sha256_and_size(dataset_path)

    git_commits: dict[str, str | None] = {}
    git_dirty: dict[str, bool | None] = {}
    for repo in SIBLING_REPOS:
        sha, dirty = _git_info(repo, warnings)
        git_commits[repo] = sha
        git_dirty[repo] = dirty

    deployment = ml_env.get("AZURE_OPENAI_DEPLOYMENT")
    endpoint = _redact_endpoint(ml_env.get("AZURE_OPENAI_ENDPOINT"))

    azure_info = _azure_deployment_info(
        resource_group=azure_resource_group,
        account_name=azure_account_name,
        deployment_name=deployment,
        warnings=warnings,
    )

    # The worker (bizstruct_ml.llm.client.LLMClient.generate_structured)
    # does not set temperature, top_p, or any other generation parameter —
    # it calls beta.chat.completions.parse() with only model/messages/
    # response_format. So there is nothing to read here; recorded as null
    # with an explicit reason rather than silently omitted.
    warnings.append(
        "temperature/generation_params: bizstruct_ml.llm.client.LLMClient does not set "
        "temperature or any other sampling parameter — the API default applies, unrecorded "
        "anywhere in the worker's own config."
    )

    return RunMeta(
        run_id=run_id,
        configuration=configuration,
        deployment=deployment,
        model_version=azure_info.get("model_version"),
        endpoint=endpoint,
        temperature=None,
        generation_params={},
        guardrails=azure_info.get("guardrails"),
        dataset_path=str(dataset_path),
        dataset_sha256=dataset_sha256,
        dataset_size=dataset_size,
        domain_version=_domain_version(warnings),
        git_commits=git_commits,
        git_dirty=git_dirty,
        concurrency=concurrency,
        project_timeout=project_timeout,
        poll_interval=poll_interval,
        worker_replicas=_worker_replicas(docker_name_prefix, warnings),
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        mode=mode,
        language=language,
        meta_warnings=warnings,
    )


def read_ml_env(env_path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE per line, '#' comments, optional
    quotes) — used only to read non-secret fields (deployment, endpoint).
    Deliberately does not shell out to `source` (avoids executing the file)."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def write_run_meta(meta: RunMeta, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "run_meta.json"
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    return path


def finalize_run_meta(out_dir: Path) -> None:
    """Stamps finished_at on the run_meta.json already written at start."""
    path = out_dir / "run_meta.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data["finished_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
