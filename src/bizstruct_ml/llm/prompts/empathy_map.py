from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.language or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate an Empathy Map for the primary customer persona who experiences the core problem.

This is the FIRST block generated for this project — nothing else exists
yet (no business model options, no canvas, no architecture). Base the
persona and every item entirely on the idea above. Do not assume or invent
a monetization model, a canvas section, or any other detail that hasn't
been generated — later blocks will build on what you produce here, not the
other way around.

Structure: six sections — says, thinks, does, feels, pains, gains.

Rules:
- Use a real job title/role as the persona (reflected consistently across items)
- 3-6 items per section
- Each item: id (integer starting from 1 within its section), and text — a
  full statement, not a single word or fragment
- Items must be grounded in specific pains from the idea"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
