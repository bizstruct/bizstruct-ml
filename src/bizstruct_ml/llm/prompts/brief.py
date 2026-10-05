"""Prompt for the `brief` stage (BMG methodology, step 1)."""

from bizstruct_domain.schemas import MAX_SEGMENTS, Brief

from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import field_guide, language_rule

SYSTEM = f"""\
You normalise a startup idea into a Brief. The Brief is an extractor and classifier of what the user wrote, \
not a creative step: do not invent facts, only organise what the description says and name what it lacks.

What the Brief holds:
1. The essence of the idea: one or two sentences, rephrased from the user's text.
2. The industry or domain, even if approximate.
3. Candidate customer segments: who the potential customer is, as far as the description shows. \
Give several candidates only when the description is ambiguous about who the customer is, never more than {MAX_SEGMENTS}; \
each candidate will get its own empathy map, so make them genuinely different segments.
4. Existing resources or assets, only if the user mentioned them (an empty list otherwise).
5. A monetization hint, only if the description contains one (null otherwise).
6. Gaps: an explicit list of what the description does not say and later steps will have to assume.

Fields:
{field_guide(Brief)}

{{language_rule}}"""


def build_messages(ctx: StageContext) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": f"The user's idea:\n\n{ctx.idea}"},
    ]
