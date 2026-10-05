"""Live judge smoke run. Marked `live`: skipped unless selected with `-m live`
and JUDGE_* are set. Never part of the default suite."""
import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.live


async def test_judge_smoke_returns_a_parsed_report():
    if not all(os.environ.get(n) for n in ("JUDGE_ENDPOINT", "JUDGE_API_KEY", "JUDGE_DEPLOYMENT")):
        pytest.skip("JUDGE_ENDPOINT / JUDGE_API_KEY / JUDGE_DEPLOYMENT not set")
    path = Path(__file__).resolve().parent.parent / "scripts" / "judge_smoke.py"
    spec = importlib.util.spec_from_file_location("judge_smoke", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    result = await module.run_smoke()
    assert result.error is None, result.error
    assert result.report is not None
