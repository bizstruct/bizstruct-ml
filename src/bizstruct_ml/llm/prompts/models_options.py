from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate exactly 3 business model options in this fixed order:
1. subscription
2. transaction_fee
3. retainer_plus_saas

The Empathy Map above is your basis for these options — do not invent a
customer or a pain point independently of it. For each model:
- target_segment must match (or be a clear sub-segment of) the persona
  implied by the Empathy Map, not a new persona
- description must name which specific pain(s) or gain(s) from the Empathy
  Map's `pains`/`gains` this model addresses — a model that doesn't map to
  a concrete Empathy Map item is not grounded enough

Each model must have:
- A compelling name (format: "Model Type · ProductName")
- tagline: short explanatory phrase
- description: 2-3 sentences about monetization, segment, value proposition —
  explicitly tying back to an Empathy Map pain/gain as described above
- target_segment: specific customer segment
- key_metric: primary success metric (e.g. MRR / NRR)
- time_to_value: how fast customer sees first result
- score: 0-100 integer representing how well this model fits the idea

Use placeholder UUIDs (will be replaced in postprocessing). Set selected_id to null."""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
