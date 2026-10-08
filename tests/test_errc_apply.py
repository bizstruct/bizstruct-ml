"""Applying the moves of an Errc to a canvas: version k -> k + 1, deterministic, no LLM."""
import uuid

import pytest
from bizstruct_domain.schemas import ARTIFACT_ID_NAMESPACE, CanvasSection, CanvasSections, ERRCActionType, ErrcMove

from bizstruct_ml.stages.errc_apply import apply_moves
from tests.support.cycle_builders import canvas_model, errc_model

NEW_ID = "canvas_v2"
CH = CanvasSection.CHANNELS


def move(action, target=None, new=None, section=CH):
    if action in (ERRCActionType.REDUCE, ERRCActionType.RAISE) and new is None:
        new = f"{target} (changed)"
    return ErrcMove(action=action, target_section=section, target_card_text=target, new_text=new, opposite_side_impact="i", rationale="r")


def v1():
    return canvas_model("canvas_v1", 1, {"channels": ["Direct sales", "Partner shops", "Web shop"]})


def apply(*moves, canvas=None):
    canvas = canvas or v1()
    return canvas, apply_moves(canvas, errc_model("row", 1, canvas.id, "swot_1", list(moves)), NEW_ID)


def texts(canvas, section="channels"):
    return [c.text for c in getattr(canvas.sections, section)]


def test_eliminate_removes_the_card():
    before, after = apply(move(ERRCActionType.ELIMINATE, "Partner shops"))
    assert texts(after) == ["Direct sales", "Web shop"]
    assert [c.id for c in after.sections.channels] == [before.sections.channels[0].id, before.sections.channels[2].id]


def test_create_appends_a_card_with_the_create_marker_and_a_derived_id():
    _, after = apply(move(ERRCActionType.CREATE, new="Pop-up stands"))
    new = after.sections.channels[-1]
    assert (new.text, new.errc_marker) == ("Pop-up stands", ERRCActionType.CREATE)
    assert new.id == str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{NEW_ID}:card:0"))


def test_new_cards_are_numbered_in_order_across_sections():
    _, after = apply(
        move(ERRCActionType.CREATE, new="first"), move(ERRCActionType.CREATE, new="second", section=CanvasSection.REVENUE_STREAMS),
    )
    ids = [after.sections.channels[-1].id, after.sections.revenue_streams[-1].id]
    assert ids == [str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{NEW_ID}:card:{n}")) for n in (0, 1)]


@pytest.mark.parametrize("action", [ERRCActionType.REDUCE, ERRCActionType.RAISE])
def test_reduce_and_raise_replace_the_text_keep_the_id_and_set_the_marker(action):
    before, after = apply(move(action, "Web shop", new="Web shop with a 2-hour pick-up promise"))
    original = before.sections.channels[2]
    card = after.sections.channels[2]
    assert (card.id, card.text, card.errc_marker) == (original.id, "Web shop with a 2-hour pick-up promise", action)
    assert texts(after) == ["Direct sales", "Partner shops", "Web shop with a 2-hour pick-up promise"]  # same place


def test_all_four_actions_in_one_step():
    before, after = apply(
        move(ERRCActionType.ELIMINATE, "Direct sales"),
        move(ERRCActionType.REDUCE, "Partner shops", new="Two partner shops only"),
        move(ERRCActionType.RAISE, "Web shop", new="Web shop open around the clock"),
        move(ERRCActionType.CREATE, new="Pop-up stands"),
    )
    assert texts(after) == ["Two partner shops only", "Web shop open around the clock", "Pop-up stands"]
    assert [c.errc_marker for c in after.sections.channels] == [ERRCActionType.REDUCE, ERRCActionType.RAISE, ERRCActionType.CREATE]
    assert [c.id for c in after.sections.channels[:2]] == [before.sections.channels[1].id, before.sections.channels[2].id]


def test_the_replaced_text_is_what_the_next_version_matches_on():
    before, v2 = apply(move(ERRCActionType.RAISE, "Web shop", new="Web shop, faster"))
    v3 = apply_moves(v2, errc_model("row", 2, v2.id, "swot_2", [move(ERRCActionType.RAISE, "Web shop, faster", new="Web shop, fastest")]), "canvas_v3")
    assert texts(v3)[2] == "Web shop, fastest" and v3.sections.channels[2].id == before.sections.channels[2].id
    with pytest.raises(ValueError, match="Move 1"):
        apply_moves(v2, errc_model("row", 2, v2.id, "swot_2", [move(ERRCActionType.RAISE, "Web shop", new="x")]), "canvas_v3")  # the old text is gone


def test_a_later_move_of_the_same_step_cannot_find_the_old_text_of_a_rewritten_card():
    with pytest.raises(ValueError, match=r"Move 2 \(raise\) targets the card 'Web shop'"):
        apply(move(ERRCActionType.RAISE, "Web shop", new="Web shop 2"), move(ERRCActionType.RAISE, "Web shop", new="Web shop 3"))


def test_cards_untouched_by_the_step_have_no_marker_even_if_an_earlier_step_marked_them():
    marked = v1()
    marked.sections.channels[0] = marked.sections.channels[0].model_copy(update={"errc_marker": ERRCActionType.RAISE})
    _, after = apply(move(ERRCActionType.RAISE, "Web shop"), canvas=marked)
    assert [c.errc_marker for c in after.sections.channels] == [None, None, ERRCActionType.RAISE]


def test_moves_apply_in_order_and_a_later_move_cannot_target_a_card_an_earlier_one_eliminated():
    with pytest.raises(ValueError, match=r"Move 2 \(raise\) targets the card 'Partner shops'.*earlier move"):
        apply(move(ERRCActionType.ELIMINATE, "Partner shops"), move(ERRCActionType.RAISE, "Partner shops"))


def test_a_move_cannot_target_a_card_that_a_move_of_this_step_created():
    with pytest.raises(ValueError, match="Move 2"):
        apply(move(ERRCActionType.CREATE, new="Brand new"), move(ERRCActionType.RAISE, "Brand new"))


@pytest.mark.parametrize("target", ["direct sales", "Direct sales ", "Nothing like it"])
def test_matching_is_by_exact_text(target):
    with pytest.raises(ValueError, match="no card with exactly that text"):
        apply(move(ERRCActionType.ELIMINATE, target))


def test_the_text_must_be_in_the_named_section():
    with pytest.raises(ValueError, match="Move 1"):
        apply(move(ERRCActionType.ELIMINATE, "Direct sales", section=CanvasSection.REVENUE_STREAMS))


def test_the_first_of_two_identical_texts_is_matched():
    canvas = canvas_model("canvas_v1", 1, {"channels": ["Same", "Same"]})
    _, after = apply(move(ERRCActionType.ELIMINATE, "Same"), canvas=canvas)
    assert [c.id for c in after.sections.channels] == [canvas.sections.channels[1].id]


def test_nothing_is_applied_partially_when_a_later_move_fails():
    canvas = v1()
    with pytest.raises(ValueError):
        apply(move(ERRCActionType.ELIMINATE, "Direct sales"), move(ERRCActionType.ELIMINATE, "missing"), canvas=canvas)
    assert texts(canvas) == ["Direct sales", "Partner shops", "Web shop"]  # the source canvas is not mutated


def test_version_chain_and_carried_fields():
    canvas = v1()
    _, after = apply(move(ERRCActionType.RAISE, "Web shop"), canvas=canvas)
    assert (after.id, after.version, after.previous_version_id, after.is_generated) == (NEW_ID, 2, canvas.id, False)
    assert after.group_id == canvas.group_id and after.empathy_map_ids == canvas.empathy_map_ids
    for name in CanvasSections.model_fields:
        assert len(getattr(after.sections, name)) == len(getattr(canvas.sections, name))
