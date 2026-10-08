"""Prompt for the `customer_scenario` stage (BMG, Design -> Scenarios, type 1)."""

from bizstruct_domain.schemas import Brief, CustomerScenarioGenerated, EmpathyMap, PricingTier, Stage

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import content_json, field_guide, language_rule

# 1 = the text merged in PR #5; 2 = segment list in the user message and the strict
# interdependence_signal rule.
PROMPT_VERSION = "2"

INTERDEPENDENCE_RULE = """\
interdependence_signal is strict. Set it to true ONLY if the value of THIS segment's offer requires another named customer segment \
of this project, one listed in the segment list of the user message, to be present as well (a two-sided or multi-sided platform: \
this segment gets value only when that other segment takes part). Set it to false when the project has a single segment, and in every \
case where this segment would use the offer independently, even if suppliers, partners or other parties are involved: parties that are \
not in the segment list are not segments of this project.
Positive example: a ride-hailing app with the segments "Riders" and "Drivers". For the Riders scenario the value exists only if Drivers \
are present, so interdependence_signal is true.
Negative examples: (a) a language-learning app with the single segment "Adult learners": false. (b) A bakery selling bread to \
"Neighbourhood households": the flour supplier is not a listed segment, so false."""

SYSTEM = f"""\
You write a customer scenario for the persona of one empathy map. A customer scenario is not an abstract profile: \
it is a miniature story of one concrete situation of use, answering who, where, when and how exactly the persona meets the offer. \
It builds on the empathy map and makes its insights tangible, so it must not contradict the persona's pains, gains, thoughts and feelings, \
or demographics.

Besides the story, the scenario gives a bridge to the business model canvas:
- channel_type and relationship_type: short labels. Prefer these where they fit: channels digital-self-service, physical, personal-direct, \
mixed; relationships self-service, automated, personal, dedicated-personal.
- pricing_tier: what the customer is ready to pay for, as a tier ({", ".join(t.value for t in PricingTier)}), null if the situation does not tell.
- interdependence_signal: see the rule below.
- open_questions: open questions the scenario raises about the canvas, in particular which channels fit best, which customer relationships \
to establish and what the customer is really willing to pay for.

{INTERDEPENDENCE_RULE}

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


def segment_position(ctx: StageContext) -> tuple[list[str], int]:
    """The project's segment candidates (from the Brief) and the index of this row's.

    The index comes from the empathy map row this row refs: that row's
    `instance_index` is defined as its candidate (ADR-0011), whereas this row's own
    `instance_index` only orders it under its parent.
    """
    candidates = brief_of(ctx).customer_segment_candidates
    refs = ctx.row.refs.get(Stage.EMPATHY_MAP, [])
    parent = ctx.rows.get(refs[0]) if len(refs) == 1 else None
    if parent is None:
        raise ContextError(f"row {ctx.row.id} needs exactly one empathy_map row in its refs and the snapshot")
    if parent.instance_index >= len(candidates):
        raise ContextError(
            f"empathy_map row {parent.id} has instance_index {parent.instance_index} "
            f"but the Brief has {len(candidates)} segment candidates"
        )
    return candidates, parent.instance_index


def segment_list(candidates: list[str], index: int) -> str:
    """The numbered segment list with this row's segment marked."""
    lines = [f"{i + 1}. {c}" + ("   <-- THIS ROW" if i == index else "") for i, c in enumerate(candidates)]
    count = len(candidates)
    header = (
        "Customer segments of this project (the project has a single segment):"
        if count == 1
        else f"Customer segments of this project ({count}); this row covers the one marked:"
    )
    return header + "\n" + "\n".join(lines)


def build_messages(ctx: StageContext) -> list[dict]:
    candidates, index = segment_position(ctx)
    parts = [
        f"Brief:\n{content_json(brief_of(ctx))}",
        segment_list(candidates, index),
        f"Empathy map:\n{content_json(own_empathy_map(ctx))}",
        "Write the customer scenario for this persona.",
    ]
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
