"""The Patterns generator: aliases, conversion, structural retries, consistency retries, judge wiring."""
import json
import uuid

import pytest
from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    ArtifactType,
    Epicenter,
    Pattern,
    Patterns,
    PatternsGenerated,
    ProjectSnapshot,
    SegmentRelationType,
    Stage,
    StageStatus,
    derive_artifact_id,
    parse_artifact,
)

from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.prompts import patterns as prompt
from bizstruct_ml.stages.patterns import group_id
from tests.support.fakes import FakeLLM
from tests.support.projects import (
    NO_FINDINGS,
    ONE,
    SHAPES,
    SPLIT_IN_THREE,
    SPLIT_IN_TWO,
    THREE_IN_ONE_MULTI_SIDED,
    Seg,
    Shape,
    group,
    multi_sided_claim_without_signal,
    pair,
    seed,
    stage_runner,
    tag,
)

ROW = "row_patterns_0"


async def run_patterns(backend, llm, judge_model=None):
    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language=backend.language, rows=backend.closure_of(ROW))
    runner = stage_runner(llm, judge_model)
    return await runner.run(backend.rows[ROW], snapshot, backend.language)


def patterns_of(outcome) -> Patterns:
    (record,) = outcome.artifacts
    assert record.type == ArtifactType.PATTERNS
    parsed = parse_artifact(record)
    assert isinstance(parsed, Patterns)
    return parsed


# -- aliases -------------------------------------------------------------------------------------------


def em_id(k: int) -> str:
    return derive_artifact_id(f"row_empathy_map_{k}", ArtifactType.EMPATHY_MAP, 0)


async def test_aliases_follow_the_empathy_row_instance_index_and_map_back_to_the_real_ids():
    backend = seed(THREE_IN_ONE_MULTI_SIDED)
    # make the id order disagree with the instance order: the row holding the first segment sorts last by id
    renamed = {"row_empathy_map_0": "row_z_first", "row_empathy_map_1": "row_a_second", "row_empathy_map_2": "row_m_third"}
    for old, new in renamed.items():
        row = backend.rows.pop(old)
        row.id = new
        backend.rows[new] = row
        for other in backend.rows.values():
            other.refs = {s: [new if i == old else i for i in ids] for s, ids in other.refs.items()}
    # and be lists the scenario and ideation rows in the opposite order: the closure order is not the segment order either
    refs = backend.rows[ROW].refs
    refs[Stage.CUSTOMER_SCENARIO].reverse()
    refs[Stage.IDEATION].reverse()
    llm = FakeLLM([THREE_IN_ONE_MULTI_SIDED.patterns])
    outcome = await run_patterns(backend, llm)
    assert outcome.success
    user = llm.calls[0]["messages"][1]["content"]
    positions = [user.index(f"{alias}: {seg.candidate}") for alias, seg in zip(("S1", "S2", "S3"), THREE_IN_ONE_MULTI_SIDED.segments)]
    assert positions == sorted(positions)
    assert "Pairs to score (3): S1-S2, S1-S3, S2-S3" in user
    # S1 is the segment of the instance_index 0 row, whatever its id
    (g,) = patterns_of(outcome).groups
    assert g.empathy_map_ids == [em_id(0), em_id(1), em_id(2)]


async def test_prompt_shows_each_segments_features_and_not_the_ids():
    backend = seed(THREE_IN_ONE_MULTI_SIDED)
    llm = FakeLLM([THREE_IN_ONE_MULTI_SIDED.patterns])
    await run_patterns(backend, llm)
    user = llm.calls[0]["messages"][1]["content"]
    assert "S1: Event hosts (persona Persona of Event hosts)" in user
    assert "channel_type: digital-self-service; relationship_type: self-service; pricing_tier: mid_market; interdependence_signal: true" in user
    assert "epicenter tags: customer_driven" in user and "What if Sponsors paid nothing?" in user
    assert em_id(0) not in user  # the model only ever sees aliases


# -- N = 1, shapes -------------------------------------------------------------------------------------


async def test_a_single_segment_has_no_pairs_and_one_group():
    backend = seed(ONE)
    llm = FakeLLM([ONE.patterns])
    outcome = await run_patterns(backend, llm)
    patterns = patterns_of(outcome)
    assert patterns.pairwise_scores == [] and len(patterns.groups) == 1
    assert patterns.groups[0].empathy_map_ids == [em_id(0)]
    assert patterns.branch_decision.value == "unified_model"
    user = llm.calls[0]["messages"][1]["content"]
    assert "Pairs to score: none (the project has a single segment)." in user
    assert "for one segment there are no pairs" in llm.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_every_shape_converts_with_the_expected_groups(shape: Shape):
    backend = seed(shape)
    outcome = await run_patterns(backend, FakeLLM([shape.patterns]))
    assert outcome.success and not outcome.consistency.has_errors
    patterns = patterns_of(outcome)
    assert [g.empathy_map_ids for g in patterns.groups] == [[em_id(n - 1) for n in members] for members in shape.groups]
    assert patterns.branch_decision.value == ("unified_model" if len(shape.groups) == 1 else "split_model")
    assert patterns.id == derive_artifact_id(ROW, ArtifactType.PATTERNS, 0)
    assert patterns.project_id == "project_001"


# -- group ids -----------------------------------------------------------------------------------------


def test_group_id_is_uuid5_of_row_and_position():
    assert group_id("row_x", 2) == str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, "row_x:group:2"))
    assert len({group_id("row_x", i) for i in range(3)}) == 3
    assert group_id("row_x", 0) != group_id("row_y", 0)


async def test_group_ids_are_stable_across_regeneration_with_different_content():
    backend = seed(SPLIT_IN_TWO)
    first = patterns_of(await run_patterns(backend, FakeLLM([SPLIT_IN_TWO.patterns])))
    changed = SPLIT_IN_TWO.patterns.model_copy(
        update={"pattern_tags": [tag(Pattern.LONG_TAIL, "Another rationale entirely.")], "pairwise_scores": [pair(1, 2, 4, 0), pair(1, 3, 0, -5), pair(2, 3, 0, -3)]}
    )
    second = patterns_of(await run_patterns(backend, FakeLLM([changed])))
    assert [g.id for g in first.groups] == [g.id for g in second.groups] == [group_id(ROW, 0), group_id(ROW, 1)]


async def test_groups_are_put_in_canonical_order_whatever_the_model_wrote():
    backend = seed(SPLIT_IN_TWO)
    shuffled = SPLIT_IN_TWO.patterns.model_copy(update={"groups": [group(3), group(2, 1)]})
    patterns = patterns_of(await run_patterns(backend, FakeLLM([shuffled])))
    assert [g.empathy_map_ids for g in patterns.groups] == [[em_id(0), em_id(1)], [em_id(2)]]
    assert patterns.groups[0].id == group_id(ROW, 0)


# -- conversion and structural errors retry ------------------------------------------------------------


async def test_an_unknown_alias_retries_with_the_message_as_feedback():
    backend = seed(SPLIT_IN_TWO)
    bad = SPLIT_IN_TWO.patterns.model_copy(update={"groups": [group(1, 2), group(9)]})
    llm = FakeLLM([bad, SPLIT_IN_TWO.patterns])
    outcome = await run_patterns(backend, llm)
    assert outcome.success and len(llm.calls) == 2
    assert "unknown alias 'S9'" in llm.calls[1]["messages"][-1]["content"]


async def test_a_group_count_mismatch_from_the_domain_conversion_retries(monkeypatch):
    from bizstruct_ml.stages import patterns as stage

    real = stage.patterns_from_generated
    calls = []

    def flaky(generated, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("Expected 2 group ids (one per generated group), got 1.")
        return real(generated, **kwargs)

    monkeypatch.setattr(stage, "patterns_from_generated", flaky)
    llm = FakeLLM([SPLIT_IN_TWO.patterns])
    outcome = await run_patterns(seed(SPLIT_IN_TWO), llm)
    assert outcome.success and len(calls) == 2
    assert "Expected 2 group ids" in llm.calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ({"pairwise_scores": [pair(1, 2, 3, 0), pair(1, 3, 1, -4)]}, "missing the pairs S2-S3"),
        ({"groups": [group(1, 2)]}, "in no group: S3"),
        ({"groups": [group(1, 2, 3)]}, "connected components"),
    ],
)
async def test_each_structural_check_retries_through_the_normal_path(mutation, expected):
    backend = seed(SPLIT_IN_TWO)
    bad = SPLIT_IN_TWO.patterns.model_copy(update=mutation)
    llm = FakeLLM([bad, SPLIT_IN_TWO.patterns])
    outcome = await run_patterns(backend, llm)
    assert outcome.success and len(llm.calls) == 2
    assert expected in llm.calls[1]["messages"][-1]["content"]


async def test_structural_errors_that_never_get_fixed_fail_the_row_with_the_message():
    bad = SPLIT_IN_TWO.patterns.model_copy(update={"groups": [group(1, 2, 3)]})
    outcome = await run_patterns(seed(SPLIT_IN_TWO), FakeLLM([bad]))
    assert not outcome.success and "connected components" in outcome.failure.message


# -- multi_sided_requires_signal ------------------------------------------------------------------------


def multi_sided_without_signal() -> Shape:
    return multi_sided_claim_without_signal()


FIXED = THREE_IN_ONE_MULTI_SIDED.patterns.model_copy(
    update={"groups": [group(1, 2, 3, relation=SegmentRelationType.SEGMENTED)], "pattern_tags": []}
)


async def test_multi_sided_without_a_signal_regenerates_once_with_the_violation_in_the_prompt():
    shape = multi_sided_without_signal()
    backend = seed(shape)
    llm = FakeLLM([shape.patterns, FIXED])
    outcome = await run_patterns(backend, llm, FakeJudgeModel([NO_FINDINGS]))
    assert outcome.success and outcome.consistency_retries == 1 and len(llm.calls) == 2
    feedback = llm.calls[1]["messages"][-1]["content"]
    assert "none of the CustomerScenario instances of its own segments has interdependence_signal=True" in feedback
    assert not outcome.consistency.has_errors
    assert patterns_of(outcome).pattern_tags == []


async def test_when_retries_run_out_the_row_still_returns_with_the_error_violation():
    shape = multi_sided_without_signal()
    llm = FakeLLM([shape.patterns])
    outcome = await run_patterns(seed(shape), llm, FakeJudgeModel([NO_FINDINGS]))
    assert outcome.success and outcome.consistency_retries == 2 and len(llm.calls) == 3
    assert outcome.consistency.has_errors
    assert [v.rule_id for v in outcome.consistency.violations if v.severity == "error"] == ["multi_sided_requires_signal"]
    assert len(outcome.artifacts) == 1  # be sends it to AWAITING_DECISION; ml does not drop the artifact


async def test_a_signal_in_any_scenario_satisfies_the_rule_so_nothing_regenerates():
    llm = FakeLLM([THREE_IN_ONE_MULTI_SIDED.patterns])
    outcome = await run_patterns(seed(THREE_IN_ONE_MULTI_SIDED), llm)
    assert outcome.consistency_retries == 0 and len(llm.calls) == 1


# -- judge wiring ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", [ONE, THREE_IN_ONE_MULTI_SIDED, SPLIT_IN_THREE], ids=lambda s: s.name)
async def test_the_ideation_judge_check_runs_once_and_sees_all_ideations(shape: Shape):
    judge_model = FakeJudgeModel([NO_FINDINGS])
    outcome = await run_patterns(seed(shape), FakeLLM([shape.patterns]), judge_model)
    assert outcome.success
    assert len(judge_model.calls) == 1  # ideation_grounds_pattern_tags only; canvas checks need a canvas
    payload = json.loads(judge_model.calls[0]["user"])
    assert len(payload["ideation"]) == len(shape.segments)
    assert "patterns" in payload


async def test_the_judge_runs_once_even_when_the_rule_regenerates():
    shape = multi_sided_without_signal()
    judge_model = FakeJudgeModel([NO_FINDINGS])
    await run_patterns(seed(shape), FakeLLM([shape.patterns, FIXED]), judge_model)
    assert len(judge_model.calls) == 1


# -- the prompt states the method ----------------------------------------------------------------------


def test_the_system_prompt_states_the_method_and_its_status():
    system = prompt.SYSTEM
    for text in ("starting proposal, not a formula from the book", "+1 if both segments have the same channel type",
                 "+2 if the interdependence signal is true in EITHER", "-2 if the price tiers are opposite",
                 "synergy + conflict >= -1", "connected component", "SKIP that term", "no buyer-type feature",
                 "synergy (0 to 5)", "conflict (-7 to 0)", "multi_sided_platform", "ad_supported", "outside_in"):
        assert text in system, text
    assert prompt.PROMPT_VERSION == "1"


async def test_the_runner_reports_the_patterns_prompt_version():
    assert stage_runner(FakeLLM([ONE.patterns])).prompt_version(Stage.PATTERNS) == "1"
