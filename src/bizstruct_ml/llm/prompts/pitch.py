"""Prompt for the `pitch` stage. There is no pitch technique in the book: the stage composes the earlier artifacts
along the structure the book gives for a business plan (hook, business model, advantages, risks, team, financials)."""

from dataclasses import dataclass

from bizstruct_domain.schemas import BusinessCase, Canvas, Patterns, PitchGenerated, Stage, Storytelling, Swot, TeamInfo

from bizstruct_ml.core.context import ContextError, gather_final
from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._canvas_view import render_canvas
from bizstruct_ml.llm.prompts._shared import content_json, field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of

PROMPT_VERSION = "1"

SYSTEM = """\
You write the pitch of a business model for investors, by composing artifacts that already exist: the story, the final canvas, the pattern tags \
and the final SWOT. You invent no new facts about the business.

The parts:
- hook: the opening, taken from the story (its customer and their problem), not a dry description of the company. No claims like "the next big thing".
- business_model_summary: the model in a few sentences along the canvas: the value proposition and the target customer segments first, then how it \
reaches customers, how it earns money and what it needs to run.
- competitive_advantages (at least one): what structurally sets this model apart from the usual way of doing it in the industry. Base them on the \
pattern tags and on the canvas; name the pattern in plain words when one applies.
- risk_analysis (at least one): each entry is a risk with how it is handled. Every risk must come from the SWOT given below: one of the weaknesses \
(negative statements) or a threat rated 3 or more. Restate it for an outside audience; do not add a risk that is not in that list.
{optional_parts}

Fields:
{fields}

{language_rule}"""

TEAM_PRESENT = """\
- team_section: REQUIRED here. Describe the people from the team information below: who they are, their roles and the experience and competences that \
fit this model. Use only what that information says."""
TEAM_ABSENT = """\
- team_section: there is no team information for this project, so team_section MUST be null."""
FINANCE_PRESENT = """\
- financial_analysis_section: REQUIRED here. Summarize the business case below: market benchmarks, sales scenarios and the cost and funding figures. \
Use only figures that are in it."""
FINANCE_ABSENT = """\
- financial_analysis_section: there is no business case for this project, so financial_analysis_section MUST be null."""


@dataclass(frozen=True)
class PitchInputs:
    storytelling: Storytelling
    canvas: Canvas
    swot: Swot
    patterns: Patterns | None
    team_info: TeamInfo | None
    business_case: BusinessCase | None


def _optional(ctx: StageContext, stage: Stage, model: type):
    """The artifact of an optional input, only when the row `refs` names exists and is DONE; a named row that is not done is an error."""
    found = None
    for row_id in ctx.row.refs.get(stage, []):
        row = ctx.rows.get(row_id)
        if row is None or row.status.value != "done" or not row.artifacts:
            raise ContextError(f"pitch row {ctx.row.id} refs {stage.value} row {row_id}, which is missing, not done or empty")
    for artifact in ctx.artifacts.get(stage, []):
        if isinstance(artifact, model):
            found = artifact
    return found


def pitch_inputs(ctx: StageContext) -> PitchInputs:
    stories = [a for a in ctx.artifacts.get(Stage.STORYTELLING, []) if isinstance(a, Storytelling)]
    if len(stories) != 1:
        raise ContextError(f"pitch row {ctx.row.id} needs exactly one storytelling among its refs, got {len(stories)}")
    canvas, swot = gather_final(ctx.row, ctx.rows)
    patterns = next((p for p in ctx.closure.get(Stage.PATTERNS, []) if isinstance(p, Patterns)), None)
    return PitchInputs(
        stories[0], canvas, swot, patterns, _optional(ctx, Stage.TEAM_INFO, TeamInfo), _optional(ctx, Stage.BUSINESS_CASE, BusinessCase)
    )


def risk_candidates(swot: Swot) -> list[str]:
    """The risks the SWOT supports, the same rule as the judge check pitch_risk_analysis_grounded_in_swot:
    a negative axis statement (score < 0) or a threat rated 3 or more."""
    lines = []
    for cluster in swot.clusters:
        for axis in sorted(cluster.axis_statements, key=lambda a: -a.importance):
            if axis.score < 0:
                lines.append(f"weakness (importance {axis.importance}): {axis.negative_statement}")
        for threat in sorted(cluster.threats, key=lambda t: -t.score):
            if threat.score >= 3:
                lines.append(f"threat {threat.question.value} (score {threat.score}): {threat.text}")
    return lines


def pattern_lines(patterns: Patterns | None) -> str:
    if patterns is None or not patterns.pattern_tags:
        return "none"
    return "\n".join(
        f"- {t.pattern.value}" + (f" ({t.subtype.value})" if t.subtype else "") + f": {t.rationale}" for t in patterns.pattern_tags
    )


def build_messages(ctx: StageContext) -> list[dict]:
    inputs = pitch_inputs(ctx)
    brief = brief_of(ctx)
    system = SYSTEM.format(
        optional_parts=(TEAM_PRESENT if inputs.team_info else TEAM_ABSENT) + "\n" + (FINANCE_PRESENT if inputs.business_case else FINANCE_ABSENT),
        fields=field_guide(PitchGenerated), language_rule=language_rule(ctx.language),
    )
    parts = [
        f"Idea: {brief.idea_summary}\nIndustry: {brief.industry}",
        "Story:\n" + inputs.storytelling.narrative_text,
        render_canvas(inputs.canvas, markers=False),
        "Pattern tags:\n" + pattern_lines(inputs.patterns),
        "Risks the SWOT supports (use only these for risk_analysis):\n" + "\n".join(f"- {r}" for r in risk_candidates(inputs.swot)),
    ]
    if inputs.team_info:
        parts.append("Team information:\n" + content_json(inputs.team_info))
    if inputs.business_case:
        parts.append("Business case:\n" + content_json(inputs.business_case))
    parts.append("Write the pitch.")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]
