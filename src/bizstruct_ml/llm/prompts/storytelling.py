"""Prompt for the `storytelling` stage (BMG, Design -> Storytelling, pp. 170-179).

Input: the FINAL canvas of the cycle (derived by the domain, never stored) and the customers it is for.
The perspective, the goal and the format are fixed by the project (see `stages/storytelling.py`).
"""

from bizstruct_domain.schemas import (
    Canvas,
    CustomerScenario,
    EmpathyMap,
    Stage,
    StorytellingGenerated,
)

from bizstruct_ml.core.context import gather_final
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._canvas_view import non_empty_sections, render_canvas, section_title
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

PROMPT_VERSION = "1"

# Rendered from the constants of stages/storytelling.py by build_system (kept out of this module's import graph).
SYSTEM = """\
You write the story of a business model: a short narrative that turns a finished canvas into something an audience can follow. It only \
retells what the canvas already contains through a plot; it changes nothing and invents no new part of the model.

Three choices are FIXED by the project for every story. Write exactly these values in the fields of the same name:
- perspective: {perspective}. The protagonist is ONE customer taken from the personas below, told through their eyes: the challenge they face, \
the jobs they want done, what they get from the offer and why they pay for it.
- goal: {goal}. The audience is investors: show a real and significant customer problem, how this model solves it and how the model earns money. Be \
concrete and calm; no hype, no promises of becoming the next market leader.
- format: {format}. The text will be shown together with images that are NOT produced here, so write text that stands on its own, in short \
paragraphs, and never refer to a picture.

The story:
- narrative_text: one story, one protagonist, about 200 to 350 words. Walk through the elements of the canvas in plot order (who the customer is, \
the problem, the value proposition, how the customer finds and reaches the offer, the relationship, what they pay, and in a sentence or two the \
resources, activities and partners that make it possible). Use the cards of the final canvas, not generic claims.
- canvas_references: the sections of the canvas that the story actually uses, each with a note saying which part of the story rests on it. Reference \
ONLY sections that have cards on the canvas below; the sections that have cards are: {sections}.

Fields:
{fields}

{language_rule}"""


def group_personas(ctx: StageContext, canvas: Canvas) -> list[tuple[EmpathyMap, CustomerScenario | None]]:
    """The personas (with their scenario) of the customers this canvas is for."""
    maps = {m.id: m for m in ctx.closure.get(Stage.EMPATHY_MAP, []) if isinstance(m, EmpathyMap)}
    scenarios = {s.empathy_map_id: s for s in ctx.closure.get(Stage.CUSTOMER_SCENARIO, []) if isinstance(s, CustomerScenario)}
    return [(maps[i], scenarios.get(i)) for i in canvas.empathy_map_ids if i in maps]


def describe_persona(em: EmpathyMap, scenario: CustomerScenario | None) -> str:
    lines = [
        f"{em.persona_name} ({em.persona_demographics})",
        f"  pains: {'; '.join(em.pains) or 'none'}",
        f"  gains: {'; '.join(em.gains) or 'none'}",
    ]
    if scenario is not None:
        lines.append(f"  a situation of use: {scenario.situation_narrative}")
    return "\n".join(lines)


def build_messages(ctx: StageContext) -> list[dict]:
    from bizstruct_ml.stages.storytelling import FORMAT, GOAL, PERSPECTIVE

    canvas, _ = gather_final(ctx.row, ctx.rows)
    sections = ", ".join(section_title(s) for s in non_empty_sections(canvas))
    system = SYSTEM.format(
        perspective=PERSPECTIVE.value, goal=GOAL.value, format=FORMAT.value, sections=sections,
        fields=field_guide(StorytellingGenerated), language_rule=language_rule(ctx.language),
    )
    brief = brief_of(ctx)
    personas = "\n\n".join(describe_persona(em, sc) for em, sc in group_personas(ctx, canvas))
    user = "\n\n".join(
        [
            f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
            "Customers this canvas is for (take the protagonist from here):\n" + personas,
            render_canvas(canvas, markers=False),
            "Write the story.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
