from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate a Business Model Canvas with all 9 sections:
key_partners, key_activities, key_resources, value_propositions,
customer_relationships, channels, customer_segments, cost_structure, revenue_streams.

Rules:
- 2-4 items per section
- Each item: id (placeholder UUID), text, is_ai_generated: true
- Be specific and concrete, include numbers/metrics where possible
- Items should be tightly related to the project idea"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
