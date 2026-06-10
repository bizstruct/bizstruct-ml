from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate exactly 3 strategic "What If" scenarios in this order:
1. Financial vector
2. Technical vector
3. Emotional vector

For each scenario:
- title: "What if we [strategic change]?" format
- description: 2-3 sentences about the alternative strategy
- value: non-financial value for the customer
- revenue: financial impact with specific numbers

Use placeholder UUIDs for id fields (will be replaced).
Color/icon/status are assigned in postprocessing — just provide the vector."""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
