"""Golden tests for the v2 stage prompts, and the prompt version in the trace metadata."""
import contextlib

import pytest
from bizstruct_domain.schemas import ArtifactType, EmpathyMap, Stage, StageStatus, derive_artifact_id

from bizstruct_ml.core.context import ContextError, gather_closure, gather_context, rows_by_id
from bizstruct_ml.core.stage_runner import StageContext, StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.prompts import brief, customer_scenario, empathy_map, ideation
from bizstruct_ml.llm.prompts._shared import content_json
from bizstruct_ml.stages import SLICE_1_GENERATORS
from tests.support.fake_backend import FakeBackend
from tests.support.fakes import FakeLLM, empathy_generated
from tests.test_slice1_stages import NO_FINDINGS, SCENARIO, brief_with, finish

GOLDEN_INTERDEPENDENCE_RULE = (
    "interdependence_signal is strict. Set it to true ONLY if the value of THIS segment's offer requires another named customer segment "
    "of this project, one listed in the segment list of the user message, to be present as well (a two-sided or multi-sided platform: "
    "this segment gets value only when that other segment takes part). Set it to false when the project has a single segment, and in every "
    "case where this segment would use the offer independently, even if suppliers, partners or other parties are involved: parties that are "
    "not in the segment list are not segments of this project.\n"
    'Positive example: a ride-hailing app with the segments "Riders" and "Drivers". For the Riders scenario the value exists only if Drivers '
    "are present, so interdependence_signal is true.\n"
    'Negative examples: (a) a language-learning app with the single segment "Adult learners": false. (b) A bakery selling bread to '
    '"Neighbourhood households": the flour supplier is not a listed segment, so false.'
)

GOLDEN_SAYS_AND_DOES_RULE = (
    "Hard boundary for says_and_does: it holds only what an observer could hear or see, that is words said aloud and visible actions. "
    "Anything the persona privately thinks, feels, fears or wants belongs in thinks_and_feels, never in says_and_does. To show the gap between "
    "public words and private thoughts, put the public words in says_and_does and the private thought in thinks_and_feels; do not restate "
    "the private thought inside says_and_does.\n"
    'Wrong in says_and_does: "Publicly she says she is fine, but privately she fears she cannot keep up." (the private fear cannot be observed).\n'
    'Right: in says_and_does "She tells other parents she is fine."; in thinks_and_feels "She fears she cannot keep up and hides it." '
    "Each field then holds one kind of content."
)


def test_the_new_rule_texts_are_golden():
    assert customer_scenario.INTERDEPENDENCE_RULE == GOLDEN_INTERDEPENDENCE_RULE
    assert empathy_map.SAYS_AND_DOES_RULE == GOLDEN_SAYS_AND_DOES_RULE


def test_the_rules_are_part_of_the_system_prompts_and_the_old_wording_is_gone():
    assert GOLDEN_INTERDEPENDENCE_RULE in customer_scenario.SYSTEM
    assert GOLDEN_SAYS_AND_DOES_RULE in empathy_map.SYSTEM
    assert "Show the gap between what is said in public" not in empathy_map.SYSTEM  # superseded by the boundary
    assert "true only if this segment's value depends on another segment being present" not in customer_scenario.SYSTEM
    assert "- interdependence_signal: see the rule below." in customer_scenario.SYSTEM


def test_the_examples_do_not_use_the_domains_of_the_evaluation_ideas():
    text = GOLDEN_INTERDEPENDENCE_RULE + GOLDEN_SAYS_AND_DOES_RULE
    for word in ("produce", "farm", "tutor", "school", "parents", "English"):
        assert word not in text.replace("other parents", "")  # "other parents" is the says_and_does example


def test_prompt_versions():
    assert (brief.PROMPT_VERSION, ideation.PROMPT_VERSION) == ("1", "1")  # text unchanged since #5
    assert (empathy_map.PROMPT_VERSION, customer_scenario.PROMPT_VERSION) == ("2", "2")
    assert {s: g.prompt_version for s, g in SLICE_1_GENERATORS.items()} == {
        Stage.BRIEF: "1", Stage.EMPATHY_MAP: "2", Stage.CUSTOMER_SCENARIO: "2", Stage.IDEATION: "1",
    }


def make_ctx(backend: FakeBackend, row_id: str) -> StageContext:
    row = backend.rows[row_id]
    rows = rows_by_id(backend.closure_of(row_id))
    return StageContext(
        project_id="project_001", idea=backend.idea, language="en", row=row,
        artifacts=gather_context(row, rows), closure=gather_closure(row, rows), rows=rows,
    )


def backend_with_maps(candidates: list[str]) -> FakeBackend:
    backend = FakeBackend()
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(candidates))])
    for k in range(len(candidates)):
        em = EmpathyMap.from_generated(
            empathy_generated(f"Persona {k}"),
            id=derive_artifact_id(f"row_empathy_map_{k}", ArtifactType.EMPATHY_MAP), project_id="project_001",
        )
        finish(backend, f"row_empathy_map_{k}", [(ArtifactType.EMPATHY_MAP, em)])
    return backend


def test_scenario_user_message_is_golden_for_three_segments_and_marks_this_row():
    backend = backend_with_maps(["Riders", "Drivers", "Dispatchers"])
    ctx = make_ctx(backend, "row_customer_scenario_1")
    system, user = customer_scenario.build_messages(ctx)
    assert user["role"] == "user"
    brief_model = ctx.closure[Stage.BRIEF][0]
    empathy = ctx.artifacts[Stage.EMPATHY_MAP][0]
    assert user["content"] == (
        f"Brief:\n{content_json(brief_model)}\n\n"
        "Customer segments of this project (3); this row covers the one marked:\n"
        "1. Riders\n"
        "2. Drivers   <-- THIS ROW\n"
        "3. Dispatchers\n\n"
        f"Empathy map:\n{content_json(empathy)}\n\n"
        "Write the customer scenario for this persona."
    )
    assert "Persona 1" in user["content"]


def test_scenario_user_message_is_golden_for_a_single_segment():
    backend = backend_with_maps(["Adult learners"])
    _, user = customer_scenario.build_messages(make_ctx(backend, "row_customer_scenario_0"))
    assert (
        "Customer segments of this project (the project has a single segment):\n1. Adult learners   <-- THIS ROW"
        in user["content"]
    )


def test_the_marker_follows_the_empathy_map_row_not_the_scenario_rows_own_index():
    backend = backend_with_maps(["Riders", "Drivers", "Dispatchers"])
    backend.rows["row_customer_scenario_2"].instance_index = 0  # a parent-relative convention would give 0
    _, user = customer_scenario.build_messages(make_ctx(backend, "row_customer_scenario_2"))
    assert "3. Dispatchers   <-- THIS ROW" in user["content"] and user["content"].count("<-- THIS ROW") == 1


def test_an_empathy_row_beyond_the_candidates_is_a_context_error():
    backend = backend_with_maps(["Riders", "Drivers"])
    backend.rows["row_empathy_map_1"].instance_index = 5
    with pytest.raises(ContextError, match="instance_index 5"):
        customer_scenario.build_messages(make_ctx(backend, "row_customer_scenario_1"))


def test_a_scenario_row_without_exactly_one_empathy_parent_is_a_context_error():
    backend = backend_with_maps(["Riders"])
    ctx = make_ctx(backend, "row_customer_scenario_0")
    ctx.rows.pop("row_empathy_map_0")
    with pytest.raises(ContextError, match="exactly one empathy_map row"):
        customer_scenario.build_messages(ctx)


def test_ideation_prompt_is_unchanged_by_the_segment_list():
    backend = backend_with_maps(["Riders", "Drivers"])
    _, user = ideation.build_messages(make_ctx(backend, "row_ideation_0"))
    assert "THIS ROW" not in user["content"]


# --- prompt version in the trace -------------------------------------------------------------

async def test_the_prompt_version_reaches_the_trace_root_and_the_generation_span(monkeypatch):
    from bizstruct_ml.observability import tracing
    from bizstruct_ml.strategies.pipeline import handle_message

    roots: list[dict] = []
    generations: list[dict] = []

    @contextlib.contextmanager
    def fake_root(**kwargs):
        roots.append(kwargs)
        yield tracing.NOOP

    @contextlib.contextmanager
    def fake_generation(name, **kwargs):
        generations.append(kwargs)
        yield tracing.NOOP

    monkeypatch.setattr(tracing, "trace_block_generation", fake_root)
    monkeypatch.setattr(tracing, "generation_span", fake_generation)
    backend = backend_with_maps(["Riders"])
    backend.rows["row_customer_scenario_0"].status = StageStatus.PENDING
    runner = StageRunner(SLICE_1_GENERATORS, FakeLLM([SCENARIO]), ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), retry_wait=0)
    await handle_message(backend.message_for("row_customer_scenario_0"), backend.client(), runner)
    assert [r["prompt_version"] for r in roots] == ["2"]
    assert [g["metadata"]["prompt_version"] for g in generations] == ["2"]


def test_trace_metadata_and_tags_carry_the_prompt_version(monkeypatch):
    from bizstruct_ml.observability import tracing
    from tests.test_tracing import _FakeClient

    fake = _FakeClient()
    tracing._client_init_attempted = True
    tracing._client = fake
    seen: dict = {}

    def capture(**kwargs):
        seen.update(kwargs)
        return contextlib.nullcontext()

    monkeypatch.setattr("langfuse.propagate_attributes", capture)
    with tracing.trace_block_generation(
        project_id="p", block="customer_scenario", mode="pipeline", attempt_number=1,
        domain_version="0.15.0", language="en", prompt_version="2",
    ):
        pass
    assert seen["metadata"]["prompt_version"] == "2" and "prompt:2" in seen["tags"]

    seen.clear()
    with tracing.trace_block_generation(
        project_id="p", block="b", mode="pipeline", attempt_number=1, domain_version="0.15.0", language="en",
    ):
        pass
    assert "prompt_version" not in seen["metadata"] and not any(t.startswith("prompt:") for t in seen["tags"])
    tracing._client = None
    tracing._client_init_attempted = False
