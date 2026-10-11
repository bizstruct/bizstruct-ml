"""The secret guard: nothing that looks like a key, token, password or connection string reaches a file."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from experiments.client import SmokeError

# What must never appear in a dump.
SECRET_PATTERNS = (re.compile(r"SharedAccessKey", re.I), re.compile(r"Endpoint=sb://", re.I), re.compile(r"sb://[\w.-]+\.servicebus", re.I))


def assert_no_secrets(text: str, secrets: list[str]) -> None:
    """Raises if the text holds a known secret value or a connection-string marker."""
    for secret in (s for s in secrets if s):
        if secret in text:
            raise SmokeError("refusing to write the dump: it contains a token or password")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise SmokeError(f"refusing to write the dump: it matches {pattern.pattern!r}")


def write_dump(project: dict[str, Any], dump_dir: Path, secrets: list[str], now: datetime | None = None) -> Path:
    text = json.dumps(project, indent=2, ensure_ascii=False)
    assert_no_secrets(text, secrets)
    dump_dir.mkdir(parents=True, exist_ok=True)
    path = dump_dir / f"{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(text, encoding="utf-8")
    return path
