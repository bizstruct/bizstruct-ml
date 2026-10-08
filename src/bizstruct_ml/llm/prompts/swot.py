"""Prompt for the SWOT half of the `swot_errc_cycle` stage (BMG, Strategy -> Evaluating Business Models).

The book's own list of strengths/weaknesses questions (pp. 217-219) is not available to this
project: strengths and weaknesses are guided only by the methodology's quadrant description
(recorded as a gap in ADR-0001). The threat questions below are the domain's fixed catalog with
the glosses written for this prompt; none is copied from the book.
"""

from bizstruct_domain.schemas import (
    SWOT_CLUSTER_SECTIONS,
    THREAT_QUESTIONS_BY_CLUSTER,
    Canvas,
    SwotGenerated,
    ThreatQuestion,
)

from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._canvas_view import render_canvas, section_title
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

# 1 = slice 3; 2 = anchored 1-5 scores for opportunities and threats.
PROMPT_VERSION = "2"

# One plain-words gloss per catalog question: what the threat is about. The model answers each for THIS canvas.
THREAT_GLOSS: dict[ThreatQuestion, str] = {
    ThreatQuestion.SUBSTITUTES_AVAILABLE: "other products or services could replace what the value propositions offer",
    ThreatQuestion.COMPETITOR_PRICE_OR_VALUE_PRESSURE: "competitors could offer a better price or more value for the same need",
    ThreatQuestion.MARGIN_PRESSURE: "the margin could be squeezed",
    ThreatQuestion.REVENUE_CONCENTRATION: "revenue depends on too few sources or customers",
    ThreatQuestion.REVENUE_STREAM_DECLINE: "a revenue stream could shrink or dry up",
    ThreatQuestion.COST_UNPREDICTABILITY: "costs are hard to foresee or to keep in check",
    ThreatQuestion.COST_OUTGROWING_REVENUE: "costs could grow faster than revenue",
    ThreatQuestion.RESOURCE_SUPPLY_DISRUPTION: "the supply of a key resource could be interrupted",
    ThreatQuestion.RESOURCE_QUALITY_RISK: "the quality of a key resource could suffer",
    ThreatQuestion.KEY_ACTIVITY_DISRUPTION: "a key activity could be interrupted",
    ThreatQuestion.ACTIVITY_QUALITY_RISK: "a key activity could be carried out badly",
    ThreatQuestion.PARTNER_LOSS: "a key partner could be lost",
    ThreatQuestion.PARTNER_DEFECTION_TO_COMPETITORS: "partners could move over to competitors",
    ThreatQuestion.PARTNER_OVER_DEPENDENCE: "the model leans too heavily on particular partners",
    ThreatQuestion.MARKET_SATURATION: "the market could become saturated",
    ThreatQuestion.MARKET_SHARE_PRESSURE: "market share could erode",
    ThreatQuestion.CUSTOMER_DEFECTION: "customers could leave",
    ThreatQuestion.COMPETITION_INTENSIFYING: "competition could become fiercer",
    ThreatQuestion.CHANNEL_THREAT_FROM_COMPETITORS: "competitors could take over or block the channels",
    ThreatQuestion.CHANNEL_IRRELEVANCE: "the channels could lose relevance for customers",
    ThreatQuestion.RELATIONSHIP_DETERIORATION: "customer relationships could deteriorate",
}


def _catalog() -> str:
    lines = []
    for cluster, questions in THREAT_QUESTIONS_BY_CLUSTER.items():
        blocks = ", ".join(section_title(s.value) for s in SWOT_CLUSTER_SECTIONS[cluster])
        lines.append(f"- cluster {cluster.value} (building blocks: {blocks}); rate exactly these {len(questions)} threats:")
        lines.extend(f"    {q.value}: {THREAT_GLOSS[q]}" for q in questions)
    return "\n".join(lines)


SYSTEM = f"""\
You evaluate one business model canvas with a SWOT analysis, grouped into four clusters of building blocks. This is a diagnosis: you judge the \
canvas as it stands and change nothing.

Where each quadrant comes from:
- Strengths and weaknesses are derived ONLY from the canvas: from what its cards say and how the blocks fit together. Do not bring in facts that \
the canvas does not contain.
- Opportunities and threats are also derived from the canvas, looking at it from the outside in, plus the idea and its industry. No external market \
report is available, so keep them to what the canvas and the industry make plausible.

For every cluster:
- axis_statements (2 to 5): each is one aspect of the cluster written twice, as a positive statement and as its negative opposite. score says which \
of the two describes THIS canvas and how strongly: 1 to 5 for the positive statement, -5 to -1 for the negative one, never 0 (you must lean one way). \
importance (1 to 10) is how much the aspect matters for the model; certainty (1 to 10) is how sure you are of your evaluation.
- opportunities (1 to 7): things the model could exploit; score 1 to 5 on the scale below.
- threats: the fixed catalog of the cluster, each question exactly once, in your own words for this canvas. text is one or two sentences about THIS \
canvas; score 1 to 5 on the scale below. A threat that the canvas gives no sign of still gets its row, with score 1.

Scale for the score of every opportunity and every threat (it replaces any other wording of the score in the field list):
- 1 = no evidence of this in the canvas.
- 3 = plausible, but not visible in the canvas.
- 5 = already visible in the canvas.
Use the whole range from 1 to 5, and use the middle values 2 and 4 as well. Do not give everything the same high score: on any real canvas many of the threats and opportunities have little or no support in it, and those get 1 or 2.

The clusters, their building blocks and the threats to rate:
{_catalog()}

Be consistent: judge version after version by the same standard, so the scores of two versions of one canvas can be compared.

Fields:
{field_guide(SwotGenerated)}

{{language_rule}}"""


def build_messages(ctx: StageContext, canvas: Canvas) -> list[dict]:
    brief = brief_of(ctx)
    user = "\n\n".join(
        [
            f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
            render_canvas(canvas),
            "Write the SWOT analysis of this canvas.",
        ]
    )
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": user},
    ]
