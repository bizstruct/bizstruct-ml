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

Every hypothesis needs TWO independent labels — do not derive one from the
other:

1. category — WHAT kind of assumption this is (Testing Business Ideas
   framework):
   - desirability: Do customers want this? — usually about
     value_propositions or customer_segments
   - viability: Will they pay for it? — usually about revenue_streams or
     the chosen monetization model
   - feasibility: Can we build it? — usually about key_resources,
     key_activities, or key_partners

2. quadrant — HOW risky this specific assumption is, on two independent
   axes: importance (how much the business model depends on it being
   true) x uncertainty (how little evidence we currently have for it).
   A hypothesis can be ANY category in ANY quadrant — e.g. a desirability
   hypothesis can be low-importance/low-uncertainty (q4) just as easily
   as a viability one can be high-importance/high-uncertainty (q1).
   Assess each hypothesis on its own merits, not by a fixed
   category->quadrant mapping:
   - q1: high importance, high uncertainty — test this first, the model
     breaks if it's wrong and we don't yet know if it's true
   - q2: high importance, low uncertainty — already fairly confident, but
     the model still depends on it
   - q3: low importance, high uncertainty — unknown, but wouldn't break
     the model even if false
   - q4: low importance, low uncertainty — safe to assume, low stakes

Rules:
- Each hypothesis MUST include a specific number, metric, or percentage,
  and must be phrased so a concrete result would clearly prove it false
  (a falsifiable claim, not a vague aspiration)
- At least 1 hypothesis per category: desirability, viability, feasibility
  (lowercase — these are the exact values bizstruct_domain.enums.
  HypothesisCategory accepts)
- id format: H<group>.<index> (e.g., H1.1, H1.2, H2.1)
- Group number matches THIS hypothesis's own quadrant number (q1->H1.x,
  q2->H2.x, q3->H3.x, q4->H4.x) — not its category"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
