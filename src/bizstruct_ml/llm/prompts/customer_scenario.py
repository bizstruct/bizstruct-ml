"""Prompt for the `customer_scenario` stage (BMG, Design -> Scenarios, type 1)."""

from bizstruct_domain.schemas import Brief, CustomerScenarioGenerated, EmpathyMap, PricingTier, Stage

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import content_json, field_guide, language_rule

SYSTEM = f"""\
You write a customer scenario for the persona of one empathy map. A customer scenario is not an abstract profile: \
it is a miniature story of one concrete situation of use, answering who, where, when and how exactly the persona meets the offer. \
It builds on the empathy map and makes its insights tangible, so it must not contradict the persona's pains, gains, thoughts and feelings, \
or demographics.

Besides the story, the scenario gives a bridge to the business model canvas:
- channel_type and relationship_type: short labels. Prefer these where they fit: channels digital-self-service, physical, personal-direct, \
mixed; relationships self-service, automated, personal, dedicated-personal.
- pricing_tier: what the customer is ready to pay for, as a tier ({", ".join(t.value for t in PricingTier)}), null if the situation does not tell.
- interdependence_signal: true only if this segment's value depends on another segment being present as well (for example a platform side), \
false otherwise.
- open_questions: open questions the scenario raises about the canvas, in particular which channels fit best, which customer relationships \
to establish and what the customer is really willing to pay for.

Fields:
{field_guide(CustomerScenarioGenerated)}

{{language_rule}}"""


def own_empathy_map(ctx: StageContext) -> EmpathyMap:
    maps = ctx.artifacts.get(Stage.EMPATHY_MAP, [])
    if len(maps) != 1 or not isinstance(maps[0], EmpathyMap):
        raise ContextError(f"row {ctx.row.id} needs exactly one empathy map, got {len(maps)}")
    return maps[0]


def brief_of(ctx: StageContext) -> Brief:
    """The Brief, reached through the empathy map's row (this stage's refs name only the empathy map)."""
    briefs = ctx.closure.get(Stage.BRIEF, [])
    if len(briefs) != 1 or not isinstance(briefs[0], Brief):
        raise ContextError(f"row {ctx.row.id} needs exactly one Brief in its closure, got {len(briefs)}")
    return briefs[0]


def build_messages(ctx: StageContext) -> list[dict]:
    parts = [f"Brief:\n{content_json(brief_of(ctx))}"]
    parts.append(f"Empathy map:\n{content_json(own_empathy_map(ctx))}")
    parts.append("Write the customer scenario for this persona.")
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
