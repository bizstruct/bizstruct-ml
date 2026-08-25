from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate 5-7 testable business hypotheses across 3 categories.

Each hypothesis must test the riskiest assumption behind a SPECIFIC part of
the Business Model Canvas, the Architecture classification, or a What-If
scenario above (whichever "applied" scenario is present) — not a generic
assumption about the idea. Prioritize assumptions where being wrong would
break the model, not ones that are merely uncertain.

Categories and quadrant mapping:
- Desirability (q1): Do customers want this? — usually about
  value_propositions or customer_segments
- Viability (q2): Will they pay for it? — usually about revenue_streams or
  the chosen monetization model
- Feasibility (q3, q4): Can we build it? — usually about key_resources,
  key_activities, or key_partners

Rules:
- Each hypothesis MUST include a specific number, metric, or percentage
- At least 1 hypothesis per category (Desirability, Viability, Feasibility)
- id format: H<group>.<index> (e.g., H1.1, H1.2, H2.1)
- Group number matches quadrant number (q1→H1.x, q2→H2.x, etc.)"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
