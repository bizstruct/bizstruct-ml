from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.translation_key or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate exactly 3 strategic "What If" scenarios in this order:
1. Financial vector
2. Technical vector
3. Emotional vector

Each scenario must propose rewriting a SPECIFIC section of the Business
Model Canvas above — not an abstract strategic idea disconnected from it.
Also take the architecture classification (epicenter/pattern) above into
account: a scenario that would change the epicenter or pattern entirely
(e.g. moving from single-sided to platform) is a valid and interesting
"what if", but say so explicitly in the description.

For each scenario:
- title: "What if we [strategic change to a named canvas section]?" format
- description: 2-3 sentences — name the canvas section(s) being rewritten
  and what changes in them
- value: non-financial value for the customer
- revenue: financial impact with specific numbers

Use placeholder UUIDs for id fields (will be replaced).
Color/icon/status are assigned in postprocessing — just provide the vector."""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
