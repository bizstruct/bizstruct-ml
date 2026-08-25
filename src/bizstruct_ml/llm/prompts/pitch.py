from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate two pitch decks: investor and client. This is the LAST block
generated — everything above (Empathy Map, Business Model Options, Canvas,
Architecture, What-If, Hypotheses, Scenario) already exists. Use it; do not
restate the idea in the abstract when a specific prior block already says
it better.

Investor deck (exactly 5 slides in this order):
1. hook — attention-grabbing opening
2. problem — the pain being solved; use the Empathy Map's `pains` directly,
   don't re-derive it from the idea
3. solution — how the product solves it; draw directly from the Canvas's
   value_propositions
4. traction — hypothetical but realistic metrics (mark as "potential" or
   "example"); ground the numbers in the Scenario's before/after metrics
   and/or the chosen model's key_metric
5. ask — what you're seeking from investors; frame the ask size/use of
   funds around the riskiest Viability/Feasibility hypotheses above (what
   this money is meant to de-risk)

Client deck (exactly 5 slides in this order):
1. opening — empathetic opening; mirror the Scenario persona's situation
2. empathy — understanding their situation; use the Empathy Map's
   `says`/`feels` items, in their voice where possible
3. transformation — how their life changes with the product; this is the
   Scenario's before -> after arc, retold as a promise to the reader
4. social_proof — hypothetical testimonials/metrics (mark as "example")
5. invitation — call to action

Rules:
- headline: max 80 characters, impact-driven
- content: 1-2 sentences, specific numbers where possible
- Generate BOTH Ukrainian (uk) and English (en) versions"""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
