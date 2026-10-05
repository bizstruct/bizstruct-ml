"""Live slice 1 dry run against the real generator (and judge, if configured).

Marked `live`: skipped unless selected with `-m live`. Runs the script in its own
process with the placeholder credentials `conftest.py` puts in the environment
removed, so the script reads the real ones from the environment or `.env`.
Makes billable API calls.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

_PLACEHOLDERS = {
    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
    "AZURE_OPENAI_API_KEY": "test-openai-key",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
}


def test_slice1_dry_run_end_to_end():
    env = {k: v for k, v in os.environ.items() if _PLACEHOLDERS.get(k) != v}
    script = Path(__file__).resolve().parent.parent / "scripts" / "slice1_dry_run.py"
    done = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=900)
    print(done.stdout[-6000:])
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
