from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate a user scenario (journey) for a concrete persona experiencing the core problem.

Structure:
- persona: name, initials (2 letters), role (job title + company type), pain_point (1 sentence)
- timeline: exactly 5 steps using ONLY these icon_key and label_key values:
  Step 1: icon_key="calendar", label_key="scenario.step.context", highlight=false
  Step 2: icon_key="target",   label_key="scenario.step.goal",    highlight=false
  Step 3: icon_key="zap",      label_key="scenario.step.action",  highlight=true
  Step 4: icon_key="check-circle", label_key="scenario.step.result", highlight=true
  Step 5: icon_key="trending-up",  label_key="scenario.step.impact", highlight=false
- metrics: before/after with specific units of measurement (time, money, percentage)

Rules:
- Use EXACTLY the icon_key and label_key values listed above — do not invent new ones
- highlight must be true only for steps 3 and 4
- Generate BOTH Ukrainian (uk) and English (en) versions"""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
