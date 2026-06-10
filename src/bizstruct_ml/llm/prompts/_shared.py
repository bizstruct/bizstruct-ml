import json
from typing import Any

from bizstruct_ml.schemas.project import ProjectState

BLOCK_LABELS = {
    "models_options": "Business Model Options",
    "canvas_data": "Business Model Canvas",
    "empathy_map": "Empathy Map",
    "hypotheses": "Hypotheses",
    "pitch": "Pitch",
    "scenario": "User Scenario",
    "what_if": "What-If Scenarios",
    "architecture": "Business Model Architecture",
}


def context_section(project: ProjectState) -> str:
    blocks = [
        "models_options",
        "canvas_data",
        "empathy_map",
        "hypotheses",
        "pitch",
        "scenario",
        "what_if",
        "architecture",
    ]
    parts: list[str] = []
    for b in blocks:
        val = project.get_block(b)
        if val is not None:
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
