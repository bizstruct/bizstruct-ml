"""Prompt for the `ideation` stage (BMG, Design -> Ideation: epicenter and "what if")."""

from bizstruct_domain.schemas import IdeationGenerated

from bizstruct_ml.core.stage_runner import StageContext
from bizstruct_ml.llm.prompts._shared import content_json, field_guide, language_rule
from bizstruct_ml.llm.prompts.customer_scenario import brief_of, own_empathy_map

# 1 = the text merged in PR #5.
PROMPT_VERSION = "1"

SYSTEM = f"""\
You do the ideation step for the persona of one empathy map. It has two independent parts that start from the same input, the Brief and the \
empathy map, and produce different things.

Part 1, the epicenter classification. Judge the signals in the Brief and the empathy map against these types:
- resource_driven: the Brief mentions an existing resource, infrastructure or partnership that can be extended or transformed.
- offer_driven: the idea is a new value proposition that forces the other parts of the business model to be rebuilt.
- customer_driven: the empathy map shows a strong, clearly expressed unmet pain of the segment, and that pain drives the idea.
- finance_driven: the Brief hints at a new monetization or pricing model, or a cost reduction, as the main driver.
- multiple_epicenter: the signals point at several epicenters at once. Then list every concrete type and add multiple_epicenter as well; \
with a single concrete type never add it.
Give the tags and a rationale that points at the signals you used.

Part 2, "what if" questions. For each significant assumption of the industry that the Brief reveals (how the industry usually works), \
ask a provocative question of the form "What if [the opposite of that assumption]?", tied to a concrete pain or gain from the empathy map \
where possible. The questions should provoke and feel hard to carry out; they are not obvious solutions. They are starting points, \
not answers: do not try to resolve them.

Fields:
{field_guide(IdeationGenerated)}

{{language_rule}}"""


def build_messages(ctx: StageContext) -> list[dict]:
    parts = [f"Brief:\n{content_json(brief_of(ctx))}"]
    parts.append(f"Empathy map:\n{content_json(own_empathy_map(ctx))}")
    parts.append("Produce the epicenter classification and the \"what if\" questions.")
    return [
        {"role": "system", "content": SYSTEM.replace("{language_rule}", language_rule(ctx.language))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
