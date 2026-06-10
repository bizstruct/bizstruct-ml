from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate 5-7 testable business hypotheses across 3 categories.

Categories and quadrant mapping:
- Desirability (q1): Do customers want this?
- Viability (q2): Will they pay for it?
- Feasibility (q3, q4): Can we build it?

Rules:
- Each hypothesis MUST include a specific number, metric, or percentage
- At least 1 hypothesis per category (Desirability, Viability, Feasibility)
- id format: H<group>.<index> (e.g., H1.1, H1.2, H2.1)
- Group number matches quadrant number (q1→H1.x, q2→H2.x, etc.)"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
