"""Apply the moves of an Errc to a canvas, deterministically (no LLM): canvas version k -> k + 1.

Semantics (read from the old what-if apply code in bizstruct-be, adapted to the domain's ErrcMove):
- moves apply in order, to the cards of version k only; a move finds its card by the EXACT text of
  `target_card_text` inside `target_section`, the first match;
- eliminate removes the card; reduce and raise keep the card (same id, same text) and set its
  `errc_marker`; create appends a card made from `new_text` with marker create;
- a move that finds no card (the text drifted, or an earlier move eliminated the card) aborts the
  step with a `ValueError` naming it; nothing is applied partially;
- cards untouched by the step keep their ids and get `errc_marker = None`: the marker says what the
  step that produced this version changed, not what older steps did;
- new cards get `uuid5(ARTIFACT_ID_NAMESPACE, f"{new_canvas_id}:card:{n}")`, n counting the new cards
  of this step from 0 in order, so regenerating the step gives the same ids.
"""

import uuid

from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    Canvas,
    CanvasCard,
    CanvasSections,
    ERRCActionType,
    Errc,
)


def apply_moves(canvas: Canvas, errc: Errc, new_canvas_id: str) -> Canvas:
    """The canvas of version `canvas.version + 1` produced by the moves of `errc` on `canvas`."""
    sections: dict[str, list[CanvasCard]] = {
        name: [card.model_copy(update={"errc_marker": None}) for card in cards]
        for name in CanvasSections.model_fields
        for cards in [getattr(canvas.sections, name)]
    }
    created = 0
    for number, move in enumerate(errc.moves, start=1):
        cards = sections[move.target_section.value]
        if move.action == ERRCActionType.CREATE:
            card_id = str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{new_canvas_id}:card:{created}"))
            created += 1
            cards.append(CanvasCard(id=card_id, text=move.new_text or "", errc_marker=ERRCActionType.CREATE))
            continue
        carried = {card.id for card in getattr(canvas.sections, move.target_section.value)}
        index = next((i for i, card in enumerate(cards) if card.id in carried and card.text == move.target_card_text), None)
        if index is None:
            raise ValueError(
                f"Move {number} ({move.action.value}) targets the card {move.target_card_text!r} in "
                f"{move.target_section.value}, but canvas version {canvas.version} has no card with exactly that "
                "text there (it may have been eliminated by an earlier move). Copy the text of an existing card exactly."
            )
        if move.action == ERRCActionType.ELIMINATE:
            del cards[index]
        else:  # reduce, raise: the card stays as it is, only its marker changes
            cards[index] = cards[index].model_copy(update={"errc_marker": move.action})
    return Canvas(
        id=new_canvas_id,
        group_id=canvas.group_id,
        empathy_map_ids=list(canvas.empathy_map_ids),
        version=canvas.version + 1,
        previous_version_id=canvas.id,
        is_generated=False,
        sections=CanvasSections(**sections),
    )

