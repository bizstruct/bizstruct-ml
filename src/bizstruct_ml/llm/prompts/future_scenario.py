"""Prompt for the `future_scenario` stage (BMG, Design -> Scenarios, type 2, pp. 186-189): a stress test of the final canvas."""

from bizstruct_domain.schemas import FutureScenarioGenerated

from bizstruct_ml.core.context import gather_final
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._canvas_view import non_empty_sections, render_canvas, section_title
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of
from bizstruct_ml.llm.prompts.errc import swot_signals

PROMPT_VERSION = "1"

SYSTEM = """\
You stress-test a finished business model against different possible futures of its environment. This is scenario planning, a diagnosis: it \
does not edit the canvas and does not propose a new model.

How to build it:
- uncertainty_drivers (2 to 4): the few factors that will shape this model's environment, that matter a lot for it and that nobody can predict \
(a technology, a regulation, customer behaviour, a cost or supply condition). Keep them few and specific to this idea; do not list known facts.
- variants (2 to 4): each is a different future made by taking extreme values of the drivers (two drivers give four combinations). Give each a short \
name and a narrative: a concrete picture of that future in a few sentences, in which the drivers take their values.
- adaptation_questions (at least one per variant): questions about how the business model would have to respond in that future, each tied to ONE \
section of the canvas. Ask about the value propositions (what would they look like), the key resources and activities (which would give an \
advantage), the revenue streams (how would money be made), the cost structure (how would it change), the key partnerships (which would work best) \
and the customer relationships (what role would they play), as far as that future makes them relevant. They are questions to think about, not answers.

Use ONLY sections that have cards on the canvas below for the adaptation questions; the sections that have cards are: {sections}.

Fields:
{fields}

{language_rule}"""


def build_messages(ctx: StageContext) -> list[dict]:
    canvas, swot = gather_final(ctx.row, ctx.rows)
    brief = brief_of(ctx)
    system = SYSTEM.format(
        sections=", ".join(section_title(s) for s in non_empty_sections(canvas)),
        fields=field_guide(FutureScenarioGenerated), language_rule=language_rule(ctx.language),
    )
    user = "\n\n".join(
        [
            f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
            render_canvas(canvas, markers=False),
            "SWOT of this canvas, as context (what is already known about its strengths and weaknesses):\n" + swot_signals(swot),
            "Write the future scenarios.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
