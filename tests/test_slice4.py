"""Slice 4: storytelling, future_scenario and pitch, per canvas, on top of the finished cycle."""
import json

import pytest
from bizstruct_domain.schemas import (
    ArtifactType,
    CanvasSection,
    ERRCActionType,
    ErrcGenerated,
    ErrcMove,
    FutureScenario,
    Pitch,
    Stage,
    StageStatus,
    Storytelling,
    StorytellingFormat,
    StorytellingGoal,
    StorytellingPerspective,
    derive_artifact_id,
    parse_artifact,
    project_status,
    ready_rows,
)

from bizstruct_ml.core.context import ContextError, gather_final, rows_by_id
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.strategies.pipeline import Action
from bizstruct_ml.stages import storytelling as story_stage
from bizstruct_ml.stages.storytelling import FORMAT, GOAL, PERSPECTIVE, check_fixed_choices
from tests.support.cycle_builders import finished_cycle
from tests.support.fake_backend import FakeBackend, all_done
from tests.support.projects import (
    NO_FINDINGS,
    ONE,
    SPLIT_IN_TWO,
    default_moves,
    future_generated,
    pitch_generated,
    scripted_llm,
    stage_runner,
    story_generated,
)

PITCH = Stage.PITCH
CYCLE = Stage.SWOT_ERRC_CYCLE
SERIES = {"v1_final": (90, 100), "v2_final": (100, 90, 95), "v5_final": (100, 95, 90, 85, 80)}


async def run_all(shape, scores, *, team=False, judge_model=None, **llm_kwargs):
    enabled = [Stage.TEAM_INFO] if team else []
    backend = FakeBackend(through=PITCH, enabled_optional=enabled)
    llm = scripted_llm(shape, scores=scores, **llm_kwargs)
    judge_model = judge_model or FakeJudgeModel([NO_FINDINGS])
    dispositions = await backend.run_to_completion(stage_runner(llm, judge_model))
    return backend, llm, judge_model, dispositions, enabled


def art(row, kind):
    return [parse_artifact(a) for a in row.artifacts if a.type == kind]


def final_version_of(backend, index=0):
    swots = art(backend.rows_of(CYCLE)[index], ArtifactType.SWOT)
    scores = [s.weighted_weakness_threat_score for s in swots]
    from bizstruct_domain.schemas import select_final_version

    return select_final_version(scores)


# -- the whole graph, per shape -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("team", [False, True], ids=["no team_info", "team_info DONE"])
@pytest.mark.parametrize("shape", [ONE, SPLIT_IN_TWO], ids=lambda s: s.name)
async def test_ready_rows_drive_every_shape_to_a_completed_project(shape, team):
    backend, llm, _, dispositions, enabled = await run_all(shape, SERIES["v2_final"], team=team)
    n_canvas = len(shape.groups)
    assert all(d.action == Action.COMPLETE and d.reason == "ResultApplied" for d in dispositions)
    assert all_done(backend) and ready_rows(list(backend.rows.values()), enabled) == ()
    for stage in (CYCLE, Stage.STORYTELLING, Stage.FUTURE_SCENARIO, PITCH):
        assert len(backend.rows_of(stage)) == n_canvas and {r.instance_index for r in backend.rows_of(stage)} == {0}
    assert project_status(list(backend.rows.values()), enabled) == "completed"
    assert (len(backend.rows_of(Stage.TEAM_INFO)) == 1) is team


async def test_a_project_without_the_enabled_optional_stage_is_not_complete_if_it_is_missing():
    backend, *_ = await run_all(ONE, SERIES["v1_final"])
    assert project_status(list(backend.rows.values()), [Stage.TEAM_INFO]) == "running"  # enabled but no row


@pytest.mark.parametrize("team", [False, True])
async def test_row_refs_follow_the_adr(team):
    backend, *_ = await run_all(SPLIT_IN_TWO, SERIES["v1_final"], team=team)
    for i, cycle in enumerate(backend.rows_of(CYCLE)):
        (story,), (future,), (pitch,) = (backend.rows_of(s)[i : i + 1] for s in (Stage.STORYTELLING, Stage.FUTURE_SCENARIO, PITCH))
        assert story.refs == {CYCLE: [cycle.id]} and future.refs == {CYCLE: [cycle.id]}
        expected = {Stage.STORYTELLING: [story.id], CYCLE: [cycle.id]}
        if team:
            expected[Stage.TEAM_INFO] = [backend.rows_of(Stage.TEAM_INFO)[0].id]
        assert pitch.refs == expected


# -- the FINAL canvas and swot are used ----------------------------------------------------------------------------------


@pytest.mark.parametrize("series", ["v1_final", "v2_final", "v5_final"])
async def test_the_final_canvas_and_swot_are_what_all_three_stages_read(series):
    backend, llm, *_ = await run_all(ONE, SERIES[series])
    final = {"v1_final": 1, "v2_final": 2, "v5_final": 5}[series]
    assert final_version_of(backend) == final
    cycle = backend.rows_of(CYCLE)[0]
    canvases = [parse_artifact(backend.rows_of(Stage.CANVAS)[0].artifacts[0]), *art(cycle, ArtifactType.CANVAS)]
    swots = sorted(art(cycle, ArtifactType.SWOT), key=lambda s: s.canvas_version)
    wanted_canvas, wanted_swot = canvases[final - 1], swots[final - 1]
    story = art(backend.rows_of(Stage.STORYTELLING)[0], ArtifactType.STORYTELLING)[0]
    future = art(backend.rows_of(Stage.FUTURE_SCENARIO)[0], ArtifactType.FUTURE_SCENARIO)[0]
    pitch = art(backend.rows_of(PITCH)[0], ArtifactType.PITCH)[0]
    assert (story.canvas_id, future.canvas_id, pitch.canvas_id, pitch.swot_id) == (wanted_canvas.id, wanted_canvas.id, wanted_canvas.id, wanted_swot.id)
    assert pitch.storytelling_id == story.id
    # and the prompts show that canvas
    for name in ("StorytellingGenerated", "FutureScenarioGenerated", "PitchGenerated"):
        call = next(c for c in llm.calls if c["schema"].__name__ == name)
        assert f"Final canvas (version {final}):" in call["messages"][1]["content"]
    if final > 1:
        assert "Cards marked [raise]" not in call["messages"][1]["content"]  # the story is told from the canvas, not about the last step


def test_gather_final_derives_v1_when_it_is_final_and_a_later_version_otherwise():
    for totals, final in (((60, 70), 1), ((90, 80, 85), 2), ((90, 80, 70, 60, 50), 5)):
        canvas_row, cycle_row, canvases, swots, _ = finished_cycle(totals)
        from bizstruct_domain.schemas import StageRow

        story = StageRow(id="row_story", stage=Stage.STORYTELLING, status=StageStatus.RUNNING, attempt_id="a", refs={CYCLE: [cycle_row.id]})
        canvas, swot = gather_final(story, rows_by_id([canvas_row, cycle_row, story]))
        assert (canvas.version, swot.canvas_version) == (final, final) and canvas.id == swot.canvas_id


def test_gather_final_on_an_unfinished_cycle_is_a_context_error():
    from bizstruct_domain.schemas import StageRow

    canvas_row, cycle_row, *_ = finished_cycle((90, 80))
    cycle_row.status = StageStatus.RUNNING
    story = StageRow(id="row_story", stage=Stage.STORYTELLING, status=StageStatus.RUNNING, attempt_id="a", refs={CYCLE: [cycle_row.id]})
    with pytest.raises(ContextError):
        gather_final(story, rows_by_id([canvas_row, cycle_row, story]))


# -- storytelling: the fixed choices -------------------------------------------------------------------------------------


def test_the_fixed_choices_are_named_constants_in_one_place():
    assert (PERSPECTIVE, GOAL, FORMAT) == (StorytellingPerspective.CUSTOMER, StorytellingGoal.PITCHING_INVESTORS, StorytellingFormat.TEXT_AND_IMAGE)


@pytest.mark.parametrize(
    ("overrides", "named"),
    [
        ({"perspective": StorytellingPerspective.COMPANY}, ["perspective must be 'customer' (fixed by the project for every story), got 'company'"]),
        ({"goal": StorytellingGoal.ENGAGING_EMPLOYEES}, ["goal must be 'pitching_investors' (fixed by the project for every story), got 'engaging_employees'"]),
        ({"format": StorytellingFormat.COMIC_STRIP}, ["format must be 'text_and_image' (fixed by the project for every story), got 'comic_strip'"]),
        (
            {"perspective": StorytellingPerspective.COMPANY, "format": StorytellingFormat.VIDEO_CLIP},
            ["perspective must be 'customer'", "format must be 'text_and_image'"],
        ),
    ],
)
def test_any_other_value_is_a_conversion_error_naming_every_field(overrides, named):
    with pytest.raises(ValueError) as e:
        check_fixed_choices(story_generated(**overrides))
    for text in named:
        assert text in str(e.value)
    assert "goal" not in str(e.value) or "goal" in overrides


def test_the_right_values_pass():
    check_fixed_choices(story_generated())


async def test_a_wrong_choice_retries_with_the_message_and_the_stored_story_has_the_fixed_values():
    state = {"n": 0}

    def story(messages, schema):
        state["n"] += 1
        return story_generated(perspective=StorytellingPerspective.COMPANY, goal=StorytellingGoal.INTRODUCING_NEW) if state["n"] == 1 else story_generated()

    backend, llm, *_ = await run_all(ONE, SERIES["v1_final"], story=story)
    calls = [c for c in llm.calls if c["schema"].__name__ == "StorytellingGenerated"]
    assert len(calls) == 2
    feedback = calls[1]["messages"][-1]["content"]
    assert "could not be used" in feedback and "perspective must be 'customer'" in feedback and "goal must be 'pitching_investors'" in feedback
    stored = art(backend.rows_of(Stage.STORYTELLING)[0], ArtifactType.STORYTELLING)[0]
    assert (stored.perspective, stored.goal, stored.format) == (PERSPECTIVE, GOAL, FORMAT)


async def test_the_prompt_states_the_fixed_values_and_names_the_non_empty_sections():
    backend, llm, *_ = await run_all(ONE, SERIES["v1_final"])
    call = next(c for c in llm.calls if c["schema"].__name__ == "StorytellingGenerated")
    system = call["messages"][0]["content"]
    assert "- perspective: customer." in system and "- goal: pitching_investors." in system and "- format: text_and_image." in system
    assert "FIXED by the project" in system and "never refer to a picture" in system
    assert "the sections that have cards are: Value propositions, Customer segments, Channels, Customer relationships, Revenue streams, Key resources, Key activities, Key partnerships, Cost structure." in system


# -- canvas_references and adaptation questions point at non-empty sections --------------------------------------------------


def errc_emptying_cost_structure(version, messages):
    moves = default_moves(version)
    if version != 1:
        return moves
    eliminate = [
        ErrcMove(action=ERRCActionType.ELIMINATE, target_section=CanvasSection.COST_STRUCTURE, target_card_text=f"cost_structure card {n}",
                 opposite_side_impact="costs are not described", rationale="a weakness")
        for n in (1, 2)
    ]
    return ErrcGenerated(moves=[*eliminate, *moves.moves])


async def test_a_story_that_references_an_empty_section_retries_with_the_rule_message():
    state = {"n": 0}

    def story(messages, schema):
        state["n"] += 1
        if state["n"] == 1:
            return story_generated(canvas_references=[
                {"section": CanvasSection.COST_STRUCTURE, "note": "the costs"}, {"section": CanvasSection.VALUE_PROPOSITIONS, "note": "the offer"}])
        return story_generated()

    backend, llm, *_ = await run_all(ONE, SERIES["v2_final"], errc=errc_emptying_cost_structure, story=story)
    assert final_version_of(backend) == 2
    calls = [c for c in llm.calls if c["schema"].__name__ == "StorytellingGenerated"]
    assert len(calls) == 2
    assert "Cost structure" not in calls[0]["messages"][0]["content"].split("the sections that have cards are:")[1].split("\n")[0]
    feedback = calls[1]["messages"][-1]["content"]
    assert "inconsistent" in feedback and "cost_structure" in feedback
    row = backend.rows_of(Stage.STORYTELLING)[0]
    assert row.status == StageStatus.DONE and not row.consistency.has_errors


async def test_adaptation_questions_on_an_empty_section_retry_too():
    from bizstruct_domain.schemas import AdaptationQuestion

    state = {"n": 0}

    def future(messages, schema):
        state["n"] += 1
        if state["n"] > 1:
            return future_generated()
        base = future_generated()
        bad = base.variants[0].model_copy(update={"adaptation_questions": [AdaptationQuestion(section=CanvasSection.COST_STRUCTURE, question="How do costs change?")]})
        return base.model_copy(update={"variants": [bad, base.variants[1]]})

    backend, llm, *_ = await run_all(ONE, SERIES["v2_final"], errc=errc_emptying_cost_structure, future=future)
    calls = [c for c in llm.calls if c["schema"].__name__ == "FutureScenarioGenerated"]
    assert len(calls) == 2 and "cost_structure" in calls[1]["messages"][-1]["content"]
    assert backend.rows_of(Stage.FUTURE_SCENARIO)[0].status == StageStatus.DONE


async def test_exhausted_retries_return_the_artifact_with_the_error_in_the_report():
    def story(messages, schema):
        return story_generated(canvas_references=[{"section": CanvasSection.COST_STRUCTURE, "note": "the costs"}])

    backend, llm, *_ = await run_all(ONE, SERIES["v2_final"], errc=errc_emptying_cost_structure, story=story)
    row = backend.rows_of(Stage.STORYTELLING)[0]
    assert len([c for c in llm.calls if c["schema"].__name__ == "StorytellingGenerated"]) == 3
    assert row.consistency.has_errors and row.status == StageStatus.AWAITING_DECISION and row.artifacts


# -- pitch: optional sections match the rows ---------------------------------------------------------------------------------


async def test_pitch_sections_are_null_without_team_info_and_present_with_it():
    without, *_ = await run_all(ONE, SERIES["v1_final"])
    pitch = art(without.rows_of(PITCH)[0], ArtifactType.PITCH)[0]
    assert (pitch.team_info_id, pitch.team_section, pitch.business_case_id, pitch.financial_analysis_section) == (None, None, None, None)
    with_team, llm, *_ = await run_all(ONE, SERIES["v1_final"], team=True)
    pitch = art(with_team.rows_of(PITCH)[0], ArtifactType.PITCH)[0]
    assert pitch.team_info_id == with_team.rows_of(Stage.TEAM_INFO)[0].artifacts[0].id and pitch.team_section
    assert pitch.business_case_id is None and pitch.financial_analysis_section is None  # no business_case generator yet
    call = next(c for c in llm.calls if c["schema"].__name__ == "PitchGenerated")
    assert "team_section: REQUIRED here" in call["messages"][0]["content"] and "Team information:" in call["messages"][1]["content"]
    assert "financial_analysis_section MUST be null" in call["messages"][0]["content"]


@pytest.mark.parametrize(
    ("team", "reply", "message"),
    [
        (False, pitch_generated(team=True), "team_section must be null because there is no team information for this project"),
        (True, pitch_generated(team=False), "team_section is required because there is a team information for this project"),
        (False, pitch_generated(finance=True), "financial_analysis_section must be null because there is no business case for this project"),
    ],
)
async def test_a_section_that_does_not_match_its_row_retries_with_a_clear_message(team, reply, message):
    state = {"n": 0}

    def pitch(messages, schema):
        state["n"] += 1
        if state["n"] == 1:
            return reply
        return pitch_generated(team=team)

    backend, llm, *_ = await run_all(ONE, SERIES["v1_final"], team=team, pitch=pitch)
    calls = [c for c in llm.calls if c["schema"].__name__ == "PitchGenerated"]
    assert len(calls) == 2 and message in calls[1]["messages"][-1]["content"]
    assert backend.rows_of(PITCH)[0].status == StageStatus.DONE


async def test_risks_offered_to_the_pitch_are_negative_axes_and_threats_of_three_or_more():
    from bizstruct_ml.llm.prompts.pitch import risk_candidates
    from tests.support.cycle_builders import swot_scoring

    swot = swot_scoring(21 + 8, "row", 1)  # 21 threats: eight points on top of the all-ones catalog => two threats rated 5
    lines = risk_candidates(swot)
    assert len(lines) == 2 and all(l.startswith("threat ") and "(score 5)" in l for l in lines)
    quiet = risk_candidates(swot_scoring(21, "row", 1))
    assert quiet == []


# -- split project, ids, parsing ------------------------------------------------------------------------------------------------


async def test_each_pitch_of_a_split_project_uses_its_own_storytelling_and_swot():
    def story(messages, schema):
        persona = next(p for p in ("Persona of Home cooks", "Persona of Hobby gardeners", "Persona of Industrial buyers") if p in messages[1]["content"])
        return story_generated(narrative_text=f"The story of {persona}.")

    backend, llm, *_ = await run_all(SPLIT_IN_TWO, SERIES["v2_final"], story=story)
    pitches = [art(r, ArtifactType.PITCH)[0] for r in backend.rows_of(PITCH)]
    stories = [art(r, ArtifactType.STORYTELLING)[0] for r in backend.rows_of(Stage.STORYTELLING)]
    assert [p.storytelling_id for p in pitches] == [s.id for s in stories] and stories[0].id != stories[1].id
    assert stories[0].narrative_text != stories[1].narrative_text
    for i, (pitch, cycle) in enumerate(zip(pitches, backend.rows_of(CYCLE))):
        swots = art(cycle, ArtifactType.SWOT)
        assert pitch.swot_id == next(s.id for s in swots if s.canvas_version == 2)
        assert pitch.canvas_id == derive_artifact_id(cycle.id, ArtifactType.CANVAS, 2)
    pitch_calls = [c for c in llm.calls if c["schema"].__name__ == "PitchGenerated"]
    assert "Home cooks" in pitch_calls[0]["messages"][1]["content"] and "Industrial buyers" in pitch_calls[1]["messages"][1]["content"]
    assert "Industrial buyers" not in pitch_calls[0]["messages"][1]["content"]


async def test_ids_follow_the_derivation_and_are_stable_on_regeneration():
    from bizstruct_domain.schemas import ProjectSnapshot

    backend, *_ = await run_all(ONE, SERIES["v2_final"])
    for stage, kind in ((Stage.STORYTELLING, ArtifactType.STORYTELLING), (Stage.FUTURE_SCENARIO, ArtifactType.FUTURE_SCENARIO), (PITCH, ArtifactType.PITCH)):
        row = backend.rows_of(stage)[0]
        assert row.artifacts[0].id == derive_artifact_id(row.id, kind, 0)
        snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
        again = await stage_runner(scripted_llm(ONE, scores=SERIES["v2_final"], story=lambda m, s: story_generated(narrative_text="Another text."))).run(row, snapshot, "en")
        assert again.success and again.artifacts[0].id == row.artifacts[0].id


async def test_every_posted_artifact_validates_and_parses():
    backend, *_ = await run_all(SPLIT_IN_TWO, SERIES["v2_final"], team=True)
    kinds = {Stage.STORYTELLING: Storytelling, Stage.FUTURE_SCENARIO: FutureScenario, PITCH: Pitch}
    for stage, model in kinds.items():
        for row in backend.rows_of(stage):
            result = next(r for r in backend.posted if r.stage_row_id == row.id)
            assert result.status == "success" and not result.consistency.has_errors
            assert [type(parse_artifact(a)) for a in result.artifacts] == [model]


# -- judge checks gatherable and advisory ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("team", [False, True])
async def test_pitch_judge_checks_run_on_the_pitch_row_with_the_final_swot(team):
    backend, _, judge_model, *_ = await run_all(ONE, SERIES["v2_final"], team=team)
    pitch_payloads = [json.loads(c["user"]) for c in judge_model.calls if "pitch" in json.loads(c["user"])]
    risk = [p for p in pitch_payloads if "swot" in p]
    sources = [p for p in pitch_payloads if "team_info" in p]
    assert len(risk) == 1 and risk[0]["swot"]["canvas_version"] == 2  # the final swot, not the last
    assert len(sources) == (1 if team else 0)
    if team:
        assert sources[0]["team_info"]["members"][0]["name"] == "Dana Founder" and sources[0]["business_case"] is None


async def test_judge_findings_stay_advisory_for_the_new_stages():
    finding = json.dumps({"score": 2, "violations": [{"rule_id": "x", "severity": "error", "message": "Odd.", "artifact_ids": ["y"]}]})
    backend, *_ = await run_all(ONE, SERIES["v1_final"], judge_model=FakeJudgeModel([finding]))
    pitch = backend.rows_of(PITCH)[0]
    assert pitch.status == StageStatus.DONE and not pitch.consistency.has_errors  # warnings only (JUDGE_BLOCKING is False)


# -- boundaries of the risk rule and of the pitch inputs -------------------------------------------------------------------------


def swot_with(axis_scores, threat_scores):
    from tests.support.cycle_builders import swot_scoring

    swot = swot_scoring(21, "row", 1)
    cluster = swot.clusters[2]
    axes = [cluster.axis_statements[0].model_copy(update={"score": s}) for s in axis_scores]
    threats = [t.model_copy(update={"score": s}) for t, s in zip(cluster.threats, threat_scores)]
    return swot.model_copy(update={"clusters": [*swot.clusters[:2], cluster.model_copy(update={"axis_statements": axes, "threats": threats + cluster.threats[len(threats):]}), *swot.clusters[3:]]})


def test_risk_candidates_take_negative_axes_and_threats_from_three_up_only():
    from bizstruct_ml.llm.prompts.pitch import risk_candidates

    lines = risk_candidates(swot_with([-1, 0, 1], [2, 3, 4]))
    assert sum(l.startswith("weakness") for l in lines) == 1
    assert sorted(l.split("(score ")[1][0] for l in lines if l.startswith("threat")) == ["3", "4"]


def pitch_ctx(refs, rows_extra=(), story_count=1):
    from bizstruct_domain.schemas import StageRow

    from bizstruct_ml.core.stage_runner import StageContext

    canvas_row, cycle_row, canvases, swots, _ = finished_cycle((60, 70))
    canvas = canvases[0]
    story = Storytelling.from_generated(story_generated(), id="story_0", canvas_id=canvas.id)
    pitch = StageRow(id="row_pitch_0", stage=PITCH, status=StageStatus.RUNNING, attempt_id="a", refs=refs)
    rows = rows_by_id([canvas_row, cycle_row, pitch, *rows_extra])
    return StageContext(project_id="p", idea="x", language="en", row=pitch, artifacts={Stage.STORYTELLING: [story] * story_count}, closure={}, rows=rows)


def test_pitch_needs_exactly_one_storytelling():
    from bizstruct_ml.llm.prompts.pitch import pitch_inputs

    refs = {CYCLE: ["row_cycle_0"]}
    pitch_inputs(pitch_ctx(refs))
    for count in (0, 2):
        with pytest.raises(ContextError, match="exactly one storytelling"):
            pitch_inputs(pitch_ctx(refs, story_count=count))


def test_a_named_optional_row_that_is_not_done_is_a_context_error_not_a_silent_null():
    from bizstruct_domain.schemas import StageRow

    from bizstruct_ml.llm.prompts.pitch import pitch_inputs

    team = StageRow(id="row_team_0", stage=Stage.TEAM_INFO, status=StageStatus.RUNNING, attempt_id="a", refs={})
    with pytest.raises(ContextError, match="not done"):
        pitch_inputs(pitch_ctx({CYCLE: ["row_cycle_0"], Stage.TEAM_INFO: ["row_team_0"]}, rows_extra=[team]))


async def test_the_future_scenario_prompt_names_the_non_empty_sections_and_shows_the_final_swot():
    backend, llm, *_ = await run_all(ONE, SERIES["v2_final"], errc=errc_emptying_cost_structure)
    call = next(c for c in llm.calls if c["schema"].__name__ == "FutureScenarioGenerated")
    system, user = call["messages"][0]["content"], call["messages"][1]["content"]
    listed = system.split("sections that have cards are:")[1].split("\n")[0]
    assert "Value propositions" in listed and "Cost structure" not in listed
    assert "SWOT of this canvas, as context" in user and "Final canvas (version 2):" in user
