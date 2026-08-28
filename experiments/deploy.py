"""Switches which Azure OpenAI deployment bizstruct-ml uses for a run — a
CLI-driven override instead of hand-editing .env each time (part B1 of the
comparative-model brief).

bizstruct_ml.config.Settings reads AZURE_OPENAI_DEPLOYMENT (and
AZURE_OPENAI_API_VERSION) once at process start via pydantic-settings —
there's no runtime override hook, and the brief says not to add one to the
worker. So the only lever this script has is the container's environment:
rewrite bizstruct-ml/.env, then recreate the container so it re-reads it.

Two things this deliberately gets right that bit us during the baseline
pilot (see experiments/README.md "Observed timing" / git history of this
file):
  - `docker restart` does NOT reload env_file — only `docker compose up
    --force-recreate` (or stop+rm+up) does. Using restart here would look
    like it worked and silently keep the old deployment.
  - .env is rewritten by parsing it into lines and reserializing, not by
    shell `>>`, which previously concatenated onto a line missing a
    trailing newline and corrupted two variables at once.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


class DeploySwitchError(Exception):
    pass


def read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        raise DeploySwitchError(f"{env_path} does not exist")
    return env_path.read_text(encoding="utf-8").splitlines()


def get_env_value(env_path: Path, key: str) -> str | None:
    for line in read_env_lines(env_path):
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            return stripped[len(key) + 1 :].strip().strip('"').strip("'")
    return None


def set_env_values(env_path: Path, updates: dict[str, str]) -> None:
    """Sets each key to its value, replacing an existing `KEY=...` line in
    place or appending a new one. Always writes a clean, newline-terminated
    file — never appends onto an existing line."""
    lines = read_env_lines(env_path)
    remaining = dict(updates)

    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched_key = next((k for k in remaining if stripped.startswith(f"{k}=")), None)
        if matched_key is not None:
            new_lines.append(f"{matched_key}={remaining.pop(matched_key)}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def switch_deployment(
    *,
    env_path: Path,
    compose_project_dir: Path,
    deployment: str,
    api_version: str | None = None,
    compose_service: str = "ml",
    container_name: str = "bizstruct_ml",
    ready_timeout: float = 60.0,
) -> None:
    """Rewrites AZURE_OPENAI_DEPLOYMENT (and optionally
    AZURE_OPENAI_API_VERSION) in .env, force-recreates the container, and
    blocks until its Service Bus consumer reports ready. No-ops (still
    recreates, to be safe) even if the value looks unchanged, since a
    previous run's failed recreate could have left the container on the
    old value."""
    updates = {"AZURE_OPENAI_DEPLOYMENT": deployment}
    if api_version:
        updates["AZURE_OPENAI_API_VERSION"] = api_version
    set_env_values(env_path, updates)

    since = _utc_now_seconds()
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", compose_service],
        cwd=compose_project_dir,
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise DeploySwitchError(
            f"docker compose up --force-recreate {compose_service} failed: {result.stderr}"
        )

    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        logs = subprocess.run(
            ["docker", "logs", container_name, "--since", str(since)],
            capture_output=True, text=True, timeout=15,
        ).stdout
        if "consumer_ready" in logs:
            return
        time.sleep(2)

    raise DeploySwitchError(
        f"{container_name} did not report consumer_ready within {ready_timeout}s of switching "
        f"to deployment={deployment!r} — check `docker logs {container_name}`"
    )


def _utc_now_seconds() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
