from bizstruct_ml.schemas.project import ProjectState
from ._shared import base_system, context_section


def build_messages(project: ProjectState) -> list[dict]:
    lang = project.language or "en"
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Generate exactly 3 ERRC alternatives (Blue Ocean Strategy's Eliminate-
Reduce-Raise-Create grid) for THIS project's own Business Model Canvas
above — every move must act on the canvas that already exists, not an
abstract idea disconnected from it.

The four ERRC actions, and what each move must reference:
- eliminate: remove an existing canvas card entirely. `target` must be the
  exact `text` of an existing card in `target_section`.
- reduce: scale back an existing canvas card (less of it, smaller scope,
  lower investment). `target` must be the exact `text` of an existing card
  in `target_section`.
- raise: significantly increase/strengthen an existing canvas card (more
  investment, higher standard, bigger emphasis). `target` must be the exact
  `text` of an existing card in `target_section`.
- create: add something the canvas doesn't have yet. `target` is the
  proposed new card's text (there is no existing card to reference).

Also take the architecture classification (epicenter/pattern) above into
account: if an alternative would shift the business to a different pattern
(e.g. single-sided to a multi-sided platform, or toward `free`/
`open_business_model`), say so explicitly in the alternative's premise —
don't leave a pattern shift implicit in the moves alone.

Requirements:
- The 3 alternatives must be genuinely different strategies, not
  variations of the same idea with different wording. Each should read as
  a distinct bet about how the business could work.
- Each alternative needs 3-6 moves, and MUST cover at least 3 of the 4
  distinct ERRC actions (eliminate/reduce/raise/create) — an alternative
  built only from `create` moves is a wishlist, not ERRC.
- Every move needs a `target_section` (one of the 9 canvas sections) and a
  short rationale explaining why this specific move serves the
  alternative's premise.
- All alternatives start as proposals: do not mark any as "chosen" — the
  user decides which (if any) to apply after generation.

Rules:
- Use placeholder UUIDs for id fields (will be replaced in postprocessing)"""
    return [
        {"role": "system", "content": base_system(lang)},
        {"role": "user", "content": user},
    ]
