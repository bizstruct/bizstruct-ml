"""Prompt for the `canvas` stage (BMG, Design -> Prototyping, the "elaborated canvas" level).

There is no dedicated Canvas-generation section in the project methodology; the prompt is
assembled from: the Prototyping levels (we generate the elaborated level only: all nine
blocks, 2-4 cards each), the dependency graph ("synthesis of all six artifacts"), the
Scenario A / Scenario B text, the Multi-Sided rule (who pays and who is subsidised comes from
Patterns, never from this step), the Patterns details, the domain field descriptions and the
standard definitions of the nine building blocks from the book.
"""

from dataclasses import dataclass

from bizstruct_domain.schemas import (
    CanvasGenerated,
    CanvasGroup,
    CustomerScenario,
    EmpathyMap,
    Ideation,
    Patterns,
    Stage,
)

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

PROMPT_VERSION = "1"

SYSTEM = f"""\
You write one business model canvas, at the elaborated level: all nine building blocks, each with 2 to 4 short cards. A canvas is a synthesis of \
what the earlier steps found for ONE group of customer segments of the project: the empathy maps (pains and gains), the customer scenarios, \
the ideation (epicenter and "what if" questions) and the Patterns step (the group's relation type and the project's pattern tags). It must \
trace back to them; it is not a fresh brainstorm.

The nine building blocks (the standard definitions of the book):
- value_propositions: the bundle of products and services that creates value for a customer segment; which customer problem it solves and which \
need it satisfies.
- customer_segments: the different groups of people or organizations the business aims to reach and serve.
- channels: how the business communicates with and reaches its segments to deliver the value proposition.
- customer_relationships: the types of relationship established with each segment.
- revenue_streams: the cash the business generates from each segment, and what each segment is willing to pay for.
- key_resources: the most important assets the business model needs to work.
- key_activities: the most important things the business must do to make the model work.
- key_partnerships: the network of suppliers and partners that make the model work.
- cost_structure: all costs incurred to operate the model, driven by the key resources, activities and partnerships.

How to fill them from the inputs:
- value_propositions come from the PAINS and GAINS of the group's empathy maps: each card answers a concrete pain or delivers a concrete gain, \
not a generic claim.
- customer_segments come from the personas of the group.
- channels and customer_relationships come from the scenarios' channel and relationship labels and from their open questions: take the open \
questions into account instead of ignoring them.
- revenue_streams come from the pricing tiers of the scenarios.
- key_resources, key_activities, key_partnerships and cost_structure follow from the value propositions, channels and relationships, and from the \
ideation (existing resources, partnerships and the "what if" questions are starting points, not answers).
- The epicenter of the ideation is EMPHASIS: let the block it points at (resource_driven: key resources; offer_driven: value propositions; \
customer_driven: customer segments and relationships; finance_driven: revenue streams and costs) be the most developed one.

Structure given by Patterns (use it, do not argue with it):
- If the group has several segments, this is ONE unified canvas with several customer segments: one customer_segments card per segment, and \
value propositions that cover each of them.
- If the group has a single segment, this is a single-segment canvas. The block needs at least two customer_segments cards: describe the same \
segment from two sides (who the customer is, and the situation or need that defines them). Never invent another segment.
- relation_type multi_sided: the value for one side depends on the other side being present, so give a value proposition for EACH side. \
Who pays and who is subsidised is decided by the Patterns step: take it only from the pattern tags and their rationales given below. If they do not \
say it, do not decide it here and do not introduce a subsidy: write revenue streams only as far as the scenarios' pricing tiers support.
- relation_type segmented or diversified: the segments pay independently; do not describe any subsidy between them.
- Pattern tags are lenses on this canvas, not extra canvases: if a tag applies (for example free with its subtype, long_tail, unbundling, \
open_business_model), let it show in the matching blocks, using the rationale of the tag.

Cards: one idea per card, short (a phrase, not a paragraph), concrete to this project, no repetition inside a block, no markers or numbering.

Fields:
{field_guide(CanvasGenerated)}

{{language_rule}}"""


@dataclass(frozen=True)
class GroupInputs:
    group: CanvasGroup
    patterns: Patterns
    maps: list[EmpathyMap]
    scenarios: dict[str, CustomerScenario]
    ideations: dict[str, Ideation]


def patterns_of(ctx: StageContext) -> Patterns:
    found = [p for p in ctx.artifacts.get(Stage.PATTERNS, []) if isinstance(p, Patterns)]
    if len(found) != 1:
        raise ContextError(f"row {ctx.row.id} needs exactly one Patterns among its refs, got {len(found)}")
    return found[0]


def group_inputs(ctx: StageContext) -> GroupInputs:
    """The row's group is `Patterns.groups[row.instance_index]`; the refs of the row must be that group's artifacts."""
    patterns = patterns_of(ctx)
    index = ctx.row.instance_index
    if not 0 <= index < len(patterns.groups):
        raise ContextError(f"canvas row {ctx.row.id} has instance_index {index} but Patterns has {len(patterns.groups)} groups")
    group = patterns.groups[index]
    by_id = {m.id: m for m in ctx.artifacts.get(Stage.EMPATHY_MAP, []) if isinstance(m, EmpathyMap)}
    if set(by_id) != set(group.empathy_map_ids):
        raise ContextError(
            f"canvas row {ctx.row.id} refs empathy maps {sorted(by_id)}, but group {index} of Patterns has {sorted(group.empathy_map_ids)}"
        )
    scenarios = {s.empathy_map_id: s for s in ctx.artifacts.get(Stage.CUSTOMER_SCENARIO, []) if isinstance(s, CustomerScenario)}
    ideations = {i.empathy_map_id: i for i in ctx.artifacts.get(Stage.IDEATION, []) if isinstance(i, Ideation)}
    for map_id in group.empathy_map_ids:
        if map_id not in scenarios or map_id not in ideations:
            raise ContextError(f"canvas row {ctx.row.id}: empathy map {map_id} has no scenario or no ideation among its refs")
    return GroupInputs(group, patterns, [by_id[i] for i in group.empathy_map_ids], scenarios, ideations)


def _bullets(items: list[str]) -> str:
    return "; ".join(items) if items else "none"


def describe_segment(position: int, em: EmpathyMap, scenario: CustomerScenario, ideation: Ideation) -> str:
    tier = scenario.pricing_tier.value if scenario.pricing_tier else "null"
    return "\n".join(
        [
            f"Segment {position + 1}: persona {em.persona_name} ({em.persona_demographics})",
            f"  pains: {_bullets(em.pains)}",
            f"  gains: {_bullets(em.gains)}",
            f"  scenario: {scenario.situation_narrative}",
            f"  channel_type: {scenario.channel_type or 'null'}; relationship_type: {scenario.relationship_type or 'null'}; pricing_tier: {tier}",
            f"  open questions: {_bullets(scenario.open_questions)}",
            f"  epicenter: {', '.join(t.value for t in ideation.epicenter.tags)} ({ideation.epicenter.rationale})",
            f"  what if: {_bullets(ideation.what_if_questions)}",
        ]
    )


def describe_patterns(inputs: GroupInputs) -> str:
    size = len(inputs.group.empathy_map_ids)
    lines = [
        f"This canvas covers {size} segment{'s' if size != 1 else ''} (a {'unified canvas with several customer segments' if size > 1 else 'single-segment canvas'}); "
        f"relation_type of the group: {inputs.group.relation_type.value}. The project has {len(inputs.patterns.groups)} canvas"
        f"{'es' if len(inputs.patterns.groups) != 1 else ''} in total.",
    ]
    if inputs.patterns.pattern_tags:
        lines.append("Pattern tags of the project:")
        for t in inputs.patterns.pattern_tags:
            subtype = f" ({t.subtype.value})" if t.subtype else ""
            lines.append(f"- {t.pattern.value}{subtype}: {t.rationale}")
    else:
        lines.append("Pattern tags of the project: none.")
    return "\n".join(lines)


def build_messages(ctx: StageContext) -> list[dict]:
    inputs = group_inputs(ctx)
    brief = brief_of(ctx)
    segments = [
        describe_segment(i, em, inputs.scenarios[em.id], inputs.ideations[em.id]) for i, em in enumerate(inputs.maps)
    ]
    parts = [
        f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
        describe_patterns(inputs),
        "\n\n".join(segments),
        "Write the canvas for this group.",
    ]
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
