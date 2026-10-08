"""Prompt for the `patterns` stage (BMG, Patterns, pp. 56-119, plus the project's own
Similarity/Synergy/Conflict criterion for the one-canvas-or-several decision).

All Patterns logic lives here and in `stages/patterns.py` so that it can be replaced when
NetScore moves into the domain. The NetScore weights and thresholds below are the
project's starting proposal (the project methodology document), not from the book.
"""

from dataclasses import dataclass
from itertools import combinations

from bizstruct_domain.schemas import (
    Brief,
    CustomerScenario,
    EmpathyMap,
    Ideation,
    PatternsGenerated,
    Stage,
    row_of_artifact,
)

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

PROMPT_VERSION = "1"

SYSTEM = f"""\
You classify the structure of one business model idea. You are given the customer segments of the project (aliases S1, S2, ...), each with \
its customer scenario and its ideation (epicenter classification and "what if" questions). You do not write creative content: you score the \
segments against each other, decide whether they share one canvas, and tag business model patterns.

IMPORTANT: the scoring method below is this project's own starting proposal, not a formula from the book Business Model Generation. Apply it \
as written, but keep the arithmetic honest: if a feature is missing for a segment, that term simply does not fire.

Step 1. Features of each segment. Read them from its scenario and ideation:
- channel type (scenario channel_type), relationship type (scenario relationship_type), price tier (scenario pricing_tier: premium, \
mid_market, low_cost, or unknown), interdependence signal (scenario interdependence_signal), epicenter tags (ideation, ignoring multiple_epicenter).
- A missing value (null) never counts as "the same" or as "opposite".

Step 2. Score every unordered pair of segments exactly once (N segments give N*(N-1)/2 pairs; for one segment there are no pairs and \
pairwise_scores is an empty list).
synergy (0 to 5) is the sum of:
  +1 if both segments have the same channel type
  +1 if both have the same relationship type
  +1 if the two share at least one epicenter tag
  +2 if the interdependence signal is true in EITHER of the two scenarios
conflict (-7 to 0) is the sum of:
  -2 if the price tiers are opposite (premium against low_cost)
  -2 if the customer relationships are opposite (dedicated-personal against self-service or automated)
  -2 if the cost-structure orientation is opposite (a cost-driven segment, one whose epicenter is finance_driven and whose tier is low_cost, \
against a value-driven segment, one whose tier is premium)
The project's method also has a -1 term for a fundamentally different buyer type (mass consumers against businesses) with incompatible \
channels. The data you are given has no buyer-type feature, so SKIP that term: never apply it.
Report synergy and conflict as the two integers; do not report their sum.
Example of the arithmetic with abstract segments A and B: same channel type, different relationship types, shared epicenter tag, no interdependence \
signal, opposite price tiers: synergy 1 + 0 + 1 + 0 = 2, conflict -2, net score 0.

Step 3. Compatibility graph. The nodes are the segments. Two segments are joined by an edge when synergy + conflict >= -1 (no hard conflict). \
Every connected component of the graph is ONE canvas, so every component is one group: a group lists the aliases of the segments in one component. \
Every alias is in exactly one group. One component means one unified model; several components mean separate canvases. \
Write the groups in this order: groups by their lowest alias number, and the aliases inside a group in ascending order. \
Check your answer against your own scores before you finish: the groups must be exactly the connected components.

Step 4. Relation type of each group:
- multi_sided: the group contains a pair with synergy + conflict >= 3 where the interdependence signal is true in at least one of the two scenarios \
(the value of one segment depends on the other being present).
- segmented: several segments with similar needs, each paying on its own; typically net score between 0 and 2 and no interdependence signal. \
Use segmented for a group of one segment as well (there is no relation to describe).
- diversified: unrelated segments with independent monetization; typically net score between -1 and 1 and no shared channels or relationship \
types. If a pair fits both segmented and diversified by net score, decide by the shared channels and relationships.

Step 5. Pattern tags: 0 to 5 tags for the whole project (not per group), each pattern at most once, each with a rationale that points at \
the epicenter tags, the "what if" questions or the scenario signals it rests on. A pattern is only tagged when the signals support it; 0 tags is a valid \
answer. Several patterns may apply at the same time and may be nested.
- unbundling: separating customer relationship, product innovation and infrastructure businesses, each with its own economics. Signals: \
resource_driven epicenter, and an internal conflict between different kinds of activity (for example, deep personal customer relationships \
together with scalable infrastructure).
- long_tail: many niche offers instead of a few hits, with cheap distribution and search. Signals: offer_driven epicenter, a wide fragmented demand.
- multi_sided_platform: two or more interdependent customer groups. Possible only if a group is multi_sided and has at least two segments; \
it needs an interdependence signal in the scenarios. Never tag it for one segment.
- free: one segment gets the offer free of charge and is financed by another part of the model. Signals: finance_driven epicenter and a subsidy \
signal. subtype is required: freemium, ad_supported (a form of the multi-sided platform) or bait_and_hook.
- open_business_model: systematic cooperation with outside partners. Signals: resource_driven epicenter and external partnerships, licensing \
or unused assets. subtype is required: outside_in (outside ideas in) or inside_out (own unused assets monetized outside).
For every other pattern subtype must be null.

Fields:
{field_guide(PatternsGenerated)}

{{language_rule}}"""


@dataclass(frozen=True)
class Segment:
    alias: str
    empathy_map: EmpathyMap
    scenario: CustomerScenario
    ideation: Ideation
    candidate: str | None


def alias_for(position: int) -> str:
    return f"S{position + 1}"


def segments_of(ctx: StageContext) -> list[Segment]:
    """The project's segments with aliases S1..SN, ordered by the `instance_index` of their empathy_map rows."""
    maps = [m for m in ctx.closure.get(Stage.EMPATHY_MAP, []) if isinstance(m, EmpathyMap)]
    scenarios = {s.empathy_map_id: s for s in ctx.artifacts.get(Stage.CUSTOMER_SCENARIO, []) if isinstance(s, CustomerScenario)}
    ideations = {i.empathy_map_id: i for i in ctx.artifacts.get(Stage.IDEATION, []) if isinstance(i, Ideation)}
    if not maps:
        raise ContextError(f"row {ctx.row.id} has no empathy maps in its closure")
    index_of: dict[str, int] = {}
    for em in maps:
        holder = row_of_artifact(ctx.rows.values(), em.id)
        if holder is None:
            raise ContextError(f"no row in the snapshot holds empathy map {em.id}")
        index_of[em.id] = holder.instance_index
    if len(set(index_of.values())) != len(maps):
        raise ContextError(f"row {ctx.row.id}: empathy map rows share an instance_index: {sorted(index_of.values())}")
    for em in maps:
        if em.id not in scenarios or em.id not in ideations:
            raise ContextError(f"empathy map {em.id} has no customer scenario or no ideation among the refs of row {ctx.row.id}")
    brief = brief_of(ctx)
    ordered = sorted(maps, key=lambda m: index_of[m.id])
    return [
        Segment(
            alias=alias_for(position),
            empathy_map=em,
            scenario=scenarios[em.id],
            ideation=ideations[em.id],
            candidate=_candidate(brief, index_of[em.id]),
        )
        for position, em in enumerate(ordered)
    ]


def _candidate(brief: Brief, index: int) -> str | None:
    candidates = brief.customer_segment_candidates
    return candidates[index] if index < len(candidates) else None


def describe(segment: Segment) -> str:
    s, i = segment.scenario, segment.ideation
    signal = "true" if s.interdependence_signal else "false"
    lines = [
        f"{segment.alias}: {segment.candidate or 'segment'} (persona {segment.empathy_map.persona_name})",
        f"  scenario: {s.situation_narrative}",
        f"  channel_type: {s.channel_type or 'null'}; relationship_type: {s.relationship_type or 'null'}; "
        f"pricing_tier: {s.pricing_tier.value if s.pricing_tier else 'null'}; interdependence_signal: {signal}",
        "  open questions: " + ("; ".join(s.open_questions) or "none"),
        f"  epicenter tags: {', '.join(t.value for t in i.epicenter.tags)}; rationale: {i.epicenter.rationale}",
        "  what if: " + (" | ".join(i.what_if_questions) or "none"),
    ]
    return "\n".join(lines)


def build_messages(ctx: StageContext) -> list[dict]:
    segments = segments_of(ctx)
    brief = brief_of(ctx)
    pairs = [f"{a.alias}-{b.alias}" for a, b in combinations(segments, 2)]
    parts = [
        f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
        f"Segments of this project ({len(segments)}):\n" + "\n\n".join(describe(s) for s in segments),
        (f"Pairs to score ({len(pairs)}): {', '.join(pairs)}" if pairs else "Pairs to score: none (the project has a single segment)."),
        "Score the pairs, form the groups, give the relation type of each group and tag the patterns.",
    ]
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
