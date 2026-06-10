from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate two pitch decks: investor and client.

Investor deck (exactly 5 slides in this order):
1. hook — attention-grabbing opening
2. problem — the pain being solved
3. solution — how the product solves it
4. traction — hypothetical but realistic metrics (mark as "potential" or "example")
5. ask — what you're seeking from investors

Client deck (exactly 5 slides in this order):
1. opening — empathetic opening
2. empathy — understanding their situation
3. transformation — how their life changes with the product
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
