"""The slice 2 dry-run script runs end to end offline (scripted LLM and judge) and reports what it promises."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from tests.support.projects import NO_FINDINGS, SPLIT_IN_TWO, THREE_IN_ONE_MULTI_SIDED, multi_sided_claim_without_signal, scripted_llm

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def report_status(path: Path) -> str:
    # the script's JSON has no row statuses; the patterns row's retries are the signal checked below
    return "awaiting_decision" if json.loads(path.read_text())["ok"] is False else "done"


@pytest.fixture
def script():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("slice2_dry_run", SCRIPTS / "slice2_dry_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.path.remove(str(SCRIPTS))


async def test_the_script_reports_groups_scenarios_tokens_and_retries(script, tmp_path, capsys):
    shape = multi_sided_claim_without_signal()
    out = tmp_path / "run.json"
    from tests.support.fakes import FakeLLM

    llm = scripted_llm(shape)
    inner = FakeLLM([llm._replies[0]])
    inner.last_usage = {"input": 10, "output": 5, "total": 15}
    code = await script.main("an idea", "en", str(out), inner=inner, judge=ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), judge_label="fake")
    assert code == 1 and report_status(out) == "awaiting_decision"  # the claim without a signal ends AWAITING_DECISION
    report = json.loads(out.read_text())
    assert report["judge"] == "fake" and len(report["scenarios"]) == 3
    assert all(s["interdependence_signal"] is False for s in report["scenarios"])
    patterns_row = report["rows"]["row_patterns_0"]
    assert patterns_row["consistency_retries"] == 2 and patterns_row["calls"] == 3
    assert sum("relation_type MULTI_SIDED" in t for t in patterns_row["triggers"]) == 2
    assert report["tokens_per_stage"]["patterns"]["calls"] == 3 and report["tokens_per_stage"]["patterns"]["total"] == 45
    printed = capsys.readouterr().out
    assert "== interdependence_signal per scenario" in printed and "== tokens per stage" in printed


async def test_a_split_project_reports_two_groups(script, tmp_path):
    from tests.support.fakes import FakeLLM

    inner = FakeLLM([scripted_llm(SPLIT_IN_TWO)._replies[0]])
    inner.last_usage = {"input": 1, "output": 1, "total": 2}
    out = tmp_path / "run.json"
    code = await script.main("x", "en", str(out), inner=inner, judge=ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), judge_label="fake")
    report = json.loads(out.read_text())
    assert code == 0 and report["branch_decision"] == "split_model"
    assert [g["segments"] for g in report["groups"]] == [["S1", "S2"], ["S3"]] and len(report["canvases"]) == 2
