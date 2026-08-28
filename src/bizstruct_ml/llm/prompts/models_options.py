from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.language or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate exactly 3 business model options in this fixed order:
1. subscription
2. transaction_fee
3. retainer_plus_saas

The Empathy Map above is your basis for these options — do not invent a
customer or a pain point independently of it. For each option:
- audience must match (or be a clear sub-segment of) the persona implied
  by the Empathy Map, not a new persona
- description must name which specific pain(s) or gain(s) from the Empathy
  Map's `pains`/`gains` this option addresses — an option that doesn't map
  to a concrete Empathy Map item is not grounded enough

Each option must have:
- title: a compelling name (format: "Model Type · ProductName")
- audience: specific customer segment (see above)
- value_proposition: one sharp sentence — what the customer gets and why
  it's worth paying for
- description: 2-3 sentences about monetization, segment, and how it fits
  the idea — explicitly tying back to an Empathy Map pain/gain as
  described above
- monetization: subscription / transaction_fee / retainer_plus_saas, in
  the fixed order given above
- key_metric: the primary success metric for THIS monetization type, not a
  generic one — examples: subscription -> MRR / NRR / churn; transaction_fee
  -> GMV / take rate; retainer_plus_saas -> ACV / renewal rate
- time_to_value: how fast the customer sees their first result, concrete
  and specific (e.g. "30 minutes to first report", "2 weeks to first
  matched partner") — not a vague phrase like "quickly"
- score: 0-100 integer, how well this option fits the idea and the
  Empathy Map's pains
- score_rationale: 1-2 sentences explaining THAT score specifically — what
  makes it strong or weak (e.g. "high: directly addresses the #1 pain and
  has a proven willingness-to-pay signal"; "moderate: solves a real pain
  but the target segment is small") — not a restatement of the number

Use placeholder UUIDs (will be replaced in postprocessing). Set selected_id to null."""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
