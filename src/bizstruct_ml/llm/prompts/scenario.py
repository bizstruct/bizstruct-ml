from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate a user scenario (journey) for a concrete persona experiencing the core problem.

Do NOT invent a new persona. The persona's role and pain_point must be the
SAME type of person as the one in the Empathy Map above (same job title/
role, facing the same core pain from its `pains` items) — this is a
narrative retelling of that persona's story, not a different customer.

Structure:
- persona: name, initials (2 letters), role (job title + company type,
  consistent with the Empathy Map persona), pain_point (1 sentence, drawn
  from the Empathy Map's `pains`)
- timeline: exactly 5 steps using ONLY these icon_key and label_key values:
  Step 1: icon_key="calendar", label_key="scenario.step.context", highlight=false
    — restate the pain_point in a concrete moment
  Step 2: icon_key="target",   label_key="scenario.step.goal",    highlight=false
  Step 3: icon_key="zap",      label_key="scenario.step.action",  highlight=true
    — the persona using the product's core value proposition (from the
    Canvas's value_propositions above) to act
  Step 4: icon_key="check-circle", label_key="scenario.step.result", highlight=true
    — the "after" state should reflect one of those value_propositions
    being delivered, not a generic improvement
  Step 5: icon_key="trending-up",  label_key="scenario.step.impact", highlight=false
- metrics: before/after with specific units of measurement (time, money,
  percentage) — the "after" metric should match the key_metric of the
  monetization model chosen in Business Model Options above where relevant

Rules:
- Use EXACTLY the icon_key and label_key values listed above — do not invent new ones
- highlight must be true only for steps 3 and 4
- Generate BOTH Ukrainian (uk) and English (en) versions"""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
