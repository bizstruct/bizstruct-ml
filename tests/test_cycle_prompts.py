"""The SWOT and ERRC prompts: what the model is shown, with a golden test for the errc_marker part."""
import pytest
from bizstruct_domain.schemas import ERRCActionType, SwotCluster, Stage, THREAT_QUESTIONS_BY_CLUSTER

from bizstruct_ml.llm.prompts import errc as errc_prompt
from bizstruct_ml.llm.prompts import swot as swot_prompt
from bizstruct_ml.llm.prompts._canvas_view import MARKER_NOTE, render_canvas
from tests.support.cycle_builders import canvas_model, swot_scoring
from tests.support.fake_backend import FakeBackend
from tests.support.projects import ONE, seed, scripted_llm, stage_runner

CH, VP = "channels", "value_propositions"


def marked_v2():
    canvas = canvas_model("c2", 2, {VP: ["Fresh boxes", "Flexible slots"], CH: ["Mobile app", "Farm stands", "Pop-up stands"]}, previous="c1")
    canvas.sections.value_propositions[0] = canvas.sections.value_propositions[0].model_copy(update={"errc_marker": ERRCActionType.RAISE})
    canvas.sections.channels[1] = canvas.sections.channels[1].model_copy(update={"errc_marker": ERRCActionType.REDUCE})
    canvas.sections.channels[2] = canvas.sections.channels[2].model_copy(update={"errc_marker": ERRCActionType.CREATE})
    return canvas


GOLDEN_V2_HEAD_AND_BLOCKS = '''Canvas version 2:
Cards marked [raise], [reduce] or [create] were changed by the previous ERRC step that produced this version; unmarked cards were not changed by it.
Value propositions:
- "Fresh boxes" [raise]
- "Flexible slots"
Customer segments:
- "customer_segments card 0"
- "customer_segments card 1"
Channels:
- "Mobile app"
- "Farm stands" [reduce]
- "Pop-up stands" [create]'''


def test_a_version_two_canvas_shows_each_cards_marker_and_says_what_the_markers_mean():
    rendered = render_canvas(marked_v2())
    assert rendered.startswith(GOLDEN_V2_HEAD_AND_BLOCKS)
    assert MARKER_NOTE in rendered


def test_a_version_one_canvas_has_no_marker_note_and_no_markers():
    rendered = render_canvas(canvas_model("c1", 1))
    assert rendered.startswith("Canvas version 1:\nValue propositions:") and "[" not in rendered and MARKER_NOTE not in rendered


def test_card_text_is_quoted_so_the_exact_text_can_be_copied_without_the_marker():
    line = [l for l in render_canvas(marked_v2()).splitlines() if "Farm stands" in l]
    assert line == ['- "Farm stands" [reduce]']


@pytest.mark.parametrize("canvas, expect_note", [(canvas_model("c1", 1), False), (marked_v2(), True)])
async def test_the_swot_user_message_carries_the_marker_part_only_from_version_two(canvas, expect_note):
    backend = seed(ONE, through=Stage.CANVAS, dispatch=False)
    ctx = await _ctx(backend)
    user = swot_prompt.build_messages(ctx, canvas)[1]["content"]
    assert (MARKER_NOTE in user) is expect_note
    assert user.endswith("Write the SWOT analysis of this canvas.")
    if expect_note:
        assert user.index('"Fresh boxes" [raise]') < user.index("Write the SWOT")


async def _ctx(backend):
    """A StageContext for a cycle row on top of a finished canvas row."""
    from bizstruct_domain.schemas import StageRow, StageStatus
    from bizstruct_ml.core.context import gather_closure, gather_context, rows_by_id
    from bizstruct_ml.core.stage_runner import StageContext

    await backend.run_to_completion(stage_runner(scripted_llm(ONE, scores=(60, 70))))
    canvas_row = backend.rows_of(Stage.CANVAS)[0]
    row = StageRow(id="row_cycle", stage=Stage.SWOT_ERRC_CYCLE, status=StageStatus.RUNNING, attempt_id="a", refs={Stage.CANVAS: [canvas_row.id]})
    backend.rows[row.id] = row
    rows = rows_by_id(backend.closure_of(row.id))
    return StageContext(project_id="project_001", idea="x", language="en", row=row, artifacts=gather_context(row, rows),
                        closure=gather_closure(row, rows), rows=rows)


def test_the_swot_system_prompt_lists_every_catalog_question_with_its_own_gloss():
    system = swot_prompt.SYSTEM
    for questions in THREAT_QUESTIONS_BY_CLUSTER.values():
        for q in questions:
            assert f"{q.value}: {swot_prompt.THREAT_GLOSS[q]}" in system
    assert len(swot_prompt.THREAT_GLOSS) == 21
    for cluster in SwotCluster:
        assert f"cluster {cluster.value}" in system
    assert "never 0" in system and "derived ONLY from the canvas" in system
    assert swot_prompt.PROMPT_VERSION == "2" and errc_prompt.PROMPT_VERSION == "2"


def test_no_gloss_repeats_a_book_sentence():
    # the glosses are short paraphrases written for this prompt
    assert all(len(g.split()) <= 14 for g in swot_prompt.THREAT_GLOSS.values())


def test_errc_prompt_asks_for_exact_card_text_and_shows_only_swot_signals():
    system = errc_prompt.SYSTEM
    for text in ("copied character for character", "Never target the same card twice", "opposite_side_impact", "eliminate", "reduce", "raise", "create"):
        assert text in system, text
    # the field rule for each action, one line each
    for line in (
        "- eliminate: target_card_text only (no new_text).",
        "- reduce and raise: target_card_text AND new_text (the card's new full text).",
        "- create: new_text only (no target_card_text).",
    ):
        assert line in system, line
    assert "it must say concretely how the level changes" in system
    assert "do not move it again unless your new_text goes further than the text it has now" in system
    assert "only its text changes" in system and "The card itself is kept as it is" not in system
    swot = swot_scoring(95, "row", 1)
    signals = errc_prompt.swot_signals(swot)
    assert signals.count("Cluster ") == 4 and "threat " in signals
    # threats rated below 3 are not signals
    low = swot_scoring(21, "row", 1)
    assert "threat " not in errc_prompt.swot_signals(low)


GOLDEN_SCALE = """Scale for the score of every opportunity and every threat (it replaces any other wording of the score in the field list):
- 1 = no evidence of this in the canvas.
- 3 = plausible, but not visible in the canvas.
- 5 = already visible in the canvas.
Use the whole range from 1 to 5, and use the middle values 2 and 4 as well. Do not give everything the same high score: on any real canvas many of the threats and opportunities have little or no support in it, and those get 1 or 2."""


def test_the_swot_prompt_anchors_the_opportunity_and_threat_scores():
    system = swot_prompt.SYSTEM
    assert GOLDEN_SCALE in system
    assert system.index(GOLDEN_SCALE) < system.index("The clusters, their building blocks and the threats to rate:")
    assert system.count("score 1 to 5 on the scale below") == 2  # opportunities and threats
    assert "barely, 5 very strongly" not in system
    # the domain scales are untouched: axis scores keep their own sign rule
    assert "1 to 5 for the positive statement, -5 to -1 for the negative one, never 0" in system


def test_the_swot_prompt_version_and_the_cycle_generators_version_string():
    from bizstruct_ml.stages.swot_errc_cycle import SwotErrcCycleGenerator

    assert SwotErrcCycleGenerator.prompt_version == "swot=2,errc=2"
