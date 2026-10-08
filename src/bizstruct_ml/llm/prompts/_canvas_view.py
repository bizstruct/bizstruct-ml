"""How a canvas is shown to the model in the swot and errc prompts."""

from bizstruct_domain.schemas import Canvas, CanvasSections

MARKER_NOTE = (
    "Cards marked [raise], [reduce] or [create] were changed by the previous ERRC step that produced this "
    "version; unmarked cards were not changed by it."
)


def section_title(name: str) -> str:
    return name.replace("_", " ").capitalize()


def non_empty_sections(canvas: Canvas) -> list[str]:
    """Names of the sections that have at least one card, in canvas order."""
    return [name for name in CanvasSections.model_fields if getattr(canvas.sections, name)]


def render_canvas(canvas: Canvas, *, markers: bool = True) -> str:
    """The canvas as text, one block per section, one line per card: the card text in double quotes
    (copy it exactly when a move targets it) and, from version 2 on, the card's errc_marker in brackets."""
    lines = [f"Canvas version {canvas.version}:" if markers else f"Final canvas (version {canvas.version}):"]
    if markers and canvas.version >= 2:
        lines.append(MARKER_NOTE)
    for name in CanvasSections.model_fields:
        lines.append(f"{section_title(name)}:")
        for card in getattr(canvas.sections, name):
            marker = f" [{card.errc_marker.value}]" if markers and card.errc_marker is not None else ""
            lines.append(f'- "{card.text}"{marker}')
    return "\n".join(lines)
