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
- persona: name, role (job title + company type, consistent with the
  Empathy Map persona), pain_point (1 sentence, drawn from the Empathy
  Map's `pains`) — each as a bilingual pair (_uk/_en fields)
- timeline: exactly 5 steps, in this EXACT order, each with the paired
  step_type/icon_key shown below:
  Step 1: step_type="context", icon_key="calendar"
    — restate the pain_point in a concrete moment
  Step 2: step_type="goal",    icon_key="target"
  Step 3: step_type="action",  icon_key="zap"
    — the persona using the product's core value proposition (from the
    Canvas's value_propositions above) to act
  Step 4: step_type="result",  icon_key="check-circle"
    — the "after" state should reflect one of those value_propositions
    being delivered, not a generic improvement
  Step 5: step_type="impact",  icon_key="trending-up"
- metrics: before/after, each with a bilingual value (_uk/_en) and a
  bilingual label (_uk/_en) naming what's measured, using specific units
  of measurement (time, money, percentage) — the "after" metric should
  match the key_metric of the monetization model chosen in Business Model
  Options above where relevant

Rules:
- Use EXACTLY the step_type/icon_key pairs and order listed above — do not
  invent new ones or reorder them
- Every text field is bilingual: provide both a Ukrainian (_uk) and an
  English (_en) version of the same content — translate, don't write
  unrelated content per language"""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
