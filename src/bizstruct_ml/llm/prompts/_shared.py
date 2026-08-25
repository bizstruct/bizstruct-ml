import json
from typing import Any

from bizstruct_domain.chain import topological_order

from bizstruct_ml.schemas.project import ProjectState

BLOCK_LABELS = {
    "models_options": "Business Model Options",
    "canvas": "Business Model Canvas",
    "empathy_map": "Empathy Map",
    "hypotheses": "Hypotheses",
    "pitch": "Pitch",
    "scenario": "User Scenario",
    "what_if": "What-If Scenarios",
    "architecture": "Business Model Architecture",
}


def _context_block_order() -> tuple[str, ...]:
    """The order blocks should appear in the context section, derived from
    bizstruct_domain.chain.topological_order(pro=False) — NOT a locally
    invented list. This used to be a hardcoded list matching the old
    (methodologically incorrect) generation order; when that order was
    fixed, this list wasn't, so the context section would present already-
    generated blocks in an order that no longer matched the sequence they
    were actually generated in. Fixed here rather than left as a prompt
    wording problem, per this task's B3.
    """
    return tuple(stage_id for stage_id in topological_order(pro=False) if stage_id in BLOCK_LABELS)


_CONTEXT_BLOCK_ORDER: tuple[str, ...] = _context_block_order()


def context_blocks_used(project: ProjectState) -> list[str]:
    """Ids of the already-generated blocks that will appear in this
    project's context section, in the order they'll appear — for both
    building the section text and for tracing (span output should record
    which blocks made it into context, not their full content)."""
    return [b for b in _CONTEXT_BLOCK_ORDER if project.get_block(b) is not None]


def context_section(project: ProjectState) -> str:
    parts: list[str] = []
    for b in context_blocks_used(project):
        val = project.get_block(b)
        label = BLOCK_LABELS.get(b, b)
        parts.append(f"### {label}\n```json\n{json.dumps(val, ensure_ascii=False, indent=2)}\n```")
    if not parts:
        return ""
    return "\n\n## Already generated context\n\n" + "\n\n".join(parts)


def base_system(language: str) -> str:
    return (
        "You are a business model generation expert.\n"
        "Return ONLY valid JSON that matches the provided schema — no prose, no markdown fences.\n"
        f"Generate content in language: {language}."
    )


def bilingual_system() -> str:
    return (
        "You are a business model generation expert.\n"
        "Return ONLY valid JSON that matches the provided schema — no prose, no markdown fences.\n"
        "Generate content in BOTH Ukrainian (uk) and English (en) simultaneously."
    )
