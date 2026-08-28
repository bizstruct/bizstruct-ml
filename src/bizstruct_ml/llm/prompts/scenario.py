from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.language or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate a user scenario (journey) for a concrete persona experiencing the core problem.

Do NOT invent a new persona. The persona's role and pain_point must be the
SAME type of person as the one in the Empathy Map above (same job title/
role, facing the same core pain from its `pains` items) — this is a
narrative retelling of that persona's story, not a different customer.

Structure:
- persona: name, role (job title + company type, consistent with the
  Empathy Map persona), pain_point (1 sentence, drawn from the Empathy
  Map's `pains`)
- timeline: exactly 5 steps, in this EXACT order:
  Step 1: step_type="context"
    — restate the pain_point in a concrete moment
  Step 2: step_type="goal"
  Step 3: step_type="action"
    — the persona using the product's core value proposition (from the
    Canvas's value_propositions above) to act
  Step 4: step_type="result"
    — the "after" state should reflect one of those value_propositions
    being delivered, not a generic improvement
  Step 5: step_type="impact"
- metrics: before/after, each with a value and a label naming what's
  measured, using specific units of measurement (time, money, percentage)
  — the "after" metric should match the key_metric of the monetization
  model chosen in Business Model Options above where relevant

Rules:
- Use EXACTLY the step_type values and order listed above — do not invent
  new ones or reorder them"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
