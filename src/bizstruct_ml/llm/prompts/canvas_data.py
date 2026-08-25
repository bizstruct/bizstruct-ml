from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate a Business Model Canvas with all 9 sections:
key_partners, key_activities, key_resources, value_propositions,
customer_relationships, channels, customer_segments, cost_structure, revenue_streams.

Use the Empathy Map and Business Model Options above as the source of truth
for three specific sections — do not invent independent content for them:
- customer_segments must describe the SAME persona/segment as the Empathy
  Map, not a new or broader one
- value_propositions must directly address the `pains` and `gains` from the
  Empathy Map — each value proposition should be traceable to a specific
  pain or gain
- revenue_streams and cost_structure must follow from the monetization
  approach(es) in Business Model Options above (subscription /
  transaction_fee / retainer_plus_saas, whichever were generated) — reuse
  their `key_metric` and pricing logic rather than proposing a different
  revenue mechanic

Rules:
- 2-4 items per section
- Each item: id (placeholder UUID), text, is_ai_generated: true
- Be specific and concrete, include numbers/metrics where possible
- Items should be tightly related to the project idea"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
