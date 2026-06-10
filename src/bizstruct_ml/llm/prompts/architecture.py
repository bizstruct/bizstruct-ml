from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate the business model architecture with two components:

1. epicenter — the primary value driver:
   Choose one: Finance-driven | Customer-driven | Offer-driven | Resource-driven | Competitor-driven
   - description: 2-3 sentences explaining WHY this epicenter fits this idea
   - status is always "determined"

2. pattern — the monetization pattern:
   Choose value from: FREE | PAID | OPEN | Multi-sided Platform | Long Tail
   - subtype: specific pattern variant (e.g., Freemium, Premium, Open Source, Bait & Hook)
   - description: 2-3 sentences explaining how this pattern works for this product
   - status is always "system_selection"

Generate BOTH Ukrainian (uk) and English (en) versions."""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
