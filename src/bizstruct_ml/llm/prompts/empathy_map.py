"""Prompt for the `empathy_map` stage (BMG, Design -> Customer Insights, empathy map by XPLANE)."""

from bizstruct_domain.schemas import Brief, EmpathyMapGenerated, Stage

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import content_json, field_guide, language_rule

SYSTEM = f"""\
You build an empathy map for one customer segment. First give the persona a name and demographic \
characteristics (such as income and family status), then fill the six parts of the map:
1. sees: the surroundings, friends, the market offers the persona meets every day (those met regularly, not the whole market), \
and the problems met.
2. hears: what friends and family say, who really influences the persona, which media channels are influential.
3. thinks_and_feels: what really matters to the persona, including what they would not say in public; emotions, worries, dreams and aspirations.
4. says_and_does: public behaviour and attitude, what the persona tells others. Show the gap between what is said in public \
and what is really thought (part 3) explicitly rather than ignoring it.
5. pains: the biggest frustrations, obstacles between the persona and the wanted result, risks the persona fears.
6. gains: what the persona actually wants to achieve, how success is measured, possible strategies for reaching the goals.

Profile only the segment you are given, as one concrete persona. Ground everything in the Brief; where the Brief is silent, \
stay plausible for the segment and do not contradict the Brief.

Fields:
{field_guide(EmpathyMapGenerated)}

{{language_rule}}"""


def segment_candidate(ctx: StageContext) -> tuple[Brief, str]:
    """The Brief and the candidate this row covers: candidate `instance_index`."""
    briefs = ctx.artifacts.get(Stage.BRIEF, [])
    if len(briefs) != 1 or not isinstance(briefs[0], Brief):
        raise ContextError(f"row {ctx.row.id} needs exactly one Brief, got {len(briefs)}")
    candidates = briefs[0].customer_segment_candidates
    index = ctx.row.instance_index
    if index >= len(candidates):
        raise ContextError(
            f"row {ctx.row.id} has instance_index {index} but the Brief has {len(candidates)} segment candidates"
        )
    return briefs[0], candidates[index]


def build_messages(ctx: StageContext) -> list[dict]:
    brief, candidate = segment_candidate(ctx)
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {
            "role": "user",
            "content": f"Brief:\n{content_json(brief)}\n\nBuild the empathy map for this segment: {candidate}",
        },
    ]
