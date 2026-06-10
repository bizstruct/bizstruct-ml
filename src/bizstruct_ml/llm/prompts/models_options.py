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

Each model must have:
- A compelling name (format: "Model Type · ProductName")
- tagline: short explanatory phrase
- description: 2-3 sentences about monetization, segment, value proposition
- target_segment: specific customer segment
- key_metric: primary success metric (e.g. MRR / NRR)
- time_to_value: how fast customer sees first result
- score: 0-100 integer representing how well this model fits the idea

Use placeholder UUIDs (will be replaced in postprocessing). Set selected_id to null."""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
