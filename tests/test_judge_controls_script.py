"""scripts/judge_controls.py without a model: the cases it builds, and the deterministic ERRC split.

Uses a real dump from smoke-dumps/ when one is present (git-ignored), else the test is skipped.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DUMPS = sorted((ROOT / "smoke-dumps").glob("*.json"))


def load_module():
    spec = importlib.util.spec_from_file_location("judge_controls", ROOT / "scripts" / "judge_controls.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def first_project_with_a_cycle(module):
    import json

    for path in DUMPS:
        project = json.loads(path.read_text())
        if any(r["stage"] == "swot_errc_cycle" and r["status"] == "done" for r in project["rows"]):
            artifacts = module.load_artifacts(project)
            if len(artifacts.get(module.ArtifactType.EMPATHY_MAP, [])) == 1:  # the persona check takes ONE pair
                return artifacts
    pytest.skip("no one-segment project dump in smoke-dumps/")


def test_cases_cover_originals_and_breaks():
    module = load_module()
    cases = module.build_cases(first_project_with_a_cycle(module))
    assert [c.expect_violation for c in cases] == [False, True, True, False, True]
    originals = {c.check_id: c for c in cases if not c.expect_violation}
    for broken in (c for c in cases if c.expect_violation):
        assert broken.inputs != originals[broken.check_id].inputs  # the break changed something


def test_errc_split_is_deterministic():
    module = load_module()
    original, broken = module.errc_split(first_project_with_a_cycle(module))
    assert original == []
    assert [v.rule_id for v in broken] == [module.ERRC_RULE]


def test_summarize_counts_misses_and_unavailable_separately():
    module = load_module()
    case = lambda expect: module.Case("c", "id", expect, ())  # noqa: E731
    results = [
        module.CaseResult(case(False), counts=[0, 1, -1]),
        module.CaseResult(case(True), counts=[2, 0, -1]),
    ]
    assert module.summarize(results) == {
        "false_alarms": 1, "original_runs": 3, "detected": 1, "broken_runs": 3, "unavailable": 2,
    }


@pytest.mark.live
async def test_live_controls_run_one_repeat():
    """Needs JUDGE_* in the environment and a dump; selected with `-m live`. One repeat only."""
    import os

    if not all(os.environ.get(n) for n in ("JUDGE_ENDPOINT", "JUDGE_API_KEY", "JUDGE_DEPLOYMENT")):
        pytest.skip("JUDGE_ENDPOINT / JUDGE_API_KEY / JUDGE_DEPLOYMENT not set")
    module = load_module()
    artifacts = first_project_with_a_cycle(module)
    model = module.build_judge()
    try:
        judge = module.ConsistencyJudge(model, max_attempts=1)
        results = [await module.run_case(judge, case, 1) for case in module.build_cases(artifacts)]
    finally:
        await model.aclose()
    assert all(len(r.counts) == 1 for r in results)
