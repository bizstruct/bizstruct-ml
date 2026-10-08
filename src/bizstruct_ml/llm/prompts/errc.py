"""Prompt for the ERRC half of the `swot_errc_cycle` stage (BMG, Business Model Perspective on Blue Ocean Strategy)."""

from bizstruct_domain.schemas import Canvas, ErrcGenerated, Swot

from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._canvas_view import render_canvas
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

PROMPT_VERSION = "1"

SYSTEM = f"""\
You propose the next step of a business model as ERRC moves (eliminate, reduce, raise, create) on the canvas you are shown, grounded in the SWOT \
analysis of that same canvas. The moves produce the next version of the canvas.

The four actions:
- eliminate: remove an element that the industry takes for granted but that the SWOT shows as a weakness or a threat, mostly in the cost-side blocks \
(key resources, key activities, key partnerships, cost structure).
- reduce: cut an element well below what is usual, same kind of signal as eliminate but less radical.
- raise: lift an element well above what is usual, driven by strengths and opportunities, mostly in the value-side blocks (value propositions, \
customer relationships, channels).
- create: add an element the industry has never offered, driven by the opportunities.

Rules for the moves (1 to 6 in total, spread over the actions that the SWOT supports; you need not use all four):
- eliminate, reduce and raise point at an EXISTING card: target_card_text must be the exact text of one card of the canvas in target_section, copied \
character for character from inside the quotes (never the bracketed marker), and new_text stays empty. The card itself is kept as it is for reduce and \
raise; only the move records the change.
- create has new_text, one short idea for a new card in target_section, and no target_card_text.
- Never target the same card twice, and never target a card that an earlier move of yours eliminates.
- opposite_side_impact: every move is checked against the opposite side of the canvas. The value side (value propositions, channels, customer \
relationships, customer segments) and the cost side (key partnerships, key activities, key resources, cost structure, with the revenue streams \
linking both) affect each other; say in one or two sentences what the move does on the other side.
- rationale: one or two sentences that name the SWOT signal (a weakness, a strength, an opportunity or a threat) the move answers.

Fields:
{field_guide(ErrcGenerated)}

{{language_rule}}"""


def swot_signals(swot: Swot) -> str:
    """The SWOT as the signals ERRC needs: weaknesses and strengths by importance, opportunities, threats rated 3 or more."""
    lines = []
    for cluster in swot.clusters:
        lines.append(f"Cluster {cluster.cluster.value}:")
        axes = sorted(cluster.axis_statements, key=lambda a: -a.importance)
        for axis in axes:
            if axis.score < 0:
                lines.append(f'  weakness (importance {axis.importance}, strength of evidence {-axis.score}): {axis.negative_statement}')
            else:
                lines.append(f'  strength (importance {axis.importance}, strength of evidence {axis.score}): {axis.positive_statement}')
        for opportunity in sorted(cluster.opportunities, key=lambda o: -o.score):
            lines.append(f"  opportunity (score {opportunity.score}): {opportunity.text}")
        for threat in sorted(cluster.threats, key=lambda t: -t.score):
            if threat.score >= 3:
                lines.append(f"  threat {threat.question.value} (score {threat.score}): {threat.text}")
    return "\n".join(lines)


def build_messages(ctx: StageContext, canvas: Canvas, swot: Swot) -> list[dict]:
    brief = brief_of(ctx)
    user = "\n\n".join(
        [
            f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
            render_canvas(canvas),
            "SWOT of this canvas version:\n" + swot_signals(swot),
            "Write the ERRC moves for the next version.",
        ]
    )
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": user},
    ]
