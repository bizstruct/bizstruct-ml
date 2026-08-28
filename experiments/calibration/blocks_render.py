"""Renders the 8 generated blocks as readable Markdown (part B of the
calibration brief: "у читабельному вигляді" — prose/lists, not raw JSON,
so a human judge reads content, not structure).

One render function per block, dispatched by block name. Field access is
defensive (.get with defaults) because a degraded project (see
calibration/degrade.py) is still expected to render even if a human
editing it by hand left a field's exact shape slightly different —
though degrade.py's own structural check is what actually guards against
that reaching this point.
"""

from __future__ import annotations

from typing import Any

CANVAS_SECTION_LABELS: dict[str, str] = {
    "key_partners": "Ключові партнери",
    "key_activities": "Ключові активності",
    "key_resources": "Ключові ресурси",
    "value_propositions": "Ціннісні пропозиції",
    "customer_relationships": "Відносини з клієнтами",
    "channels": "Канали",
    "customer_segments": "Сегменти клієнтів",
    "cost_structure": "Структура витрат",
    "revenue_streams": "Потоки доходів",
}

CANVAS_SECTION_ORDER = list(CANVAS_SECTION_LABELS.keys())

EMPATHY_SECTION_LABELS: dict[str, str] = {
    "says": "Каже",
    "thinks": "Думає",
    "does": "Робить",
    "feels": "Відчуває",
    "pains": "Болі",
    "gains": "Вигоди",
}
EMPATHY_SECTION_ORDER = list(EMPATHY_SECTION_LABELS.keys())


def _render_empathy_map(data: dict) -> list[str]:
    lines = ["## Блок: Карта емпатії", ""]
    for key in EMPATHY_SECTION_ORDER:
        items = data.get(key, [])
        lines.append(f"**{EMPATHY_SECTION_LABELS[key]}**")
        for item in items:
            lines.append(f"- {item.get('text', '')}")
        lines.append("")
    return lines


def _render_models_options(data: dict) -> list[str]:
    lines = ["## Блок: Варіанти бізнес-моделі", ""]
    for opt in data.get("options", []):
        lines.append(f"### {opt.get('title', '')}")
        lines.append(f"- Аудиторія: {opt.get('audience', '')}")
        lines.append(f"- Ціннісна пропозиція: {opt.get('value_proposition', '')}")
        lines.append(f"- Опис: {opt.get('description', '')}")
        lines.append(f"- Монетизація: {opt.get('monetization', '')}")
        lines.append(f"- Ключова метрика: {opt.get('key_metric', '')}")
        lines.append(f"- Час до цінності: {opt.get('time_to_value', '')}")
        lines.append(f"- Оцінка: {opt.get('score', '')} — {opt.get('score_rationale', '')}")
        lines.append("")
    return lines


def _render_canvas(data: dict) -> list[str]:
    lines = ["## Блок: Бізнес-модель канвас", ""]
    for key in CANVAS_SECTION_ORDER:
        items = data.get(key, [])
        lines.append(f"**{CANVAS_SECTION_LABELS[key]}**")
        for item in items:
            lines.append(f"- {item.get('text', '')}")
        lines.append("")
    return lines


def _render_architecture(data: dict) -> list[str]:
    lines = ["## Блок: Архітектура моделі", ""]
    lines.append(f"**Епіцентр:** {data.get('epicenter', '')}")
    lines.append("")
    lines.append(data.get("epicenter_rationale", ""))
    lines.append("")
    pattern = data.get("pattern", "")
    subtype = data.get("pattern_subtype")
    lines.append(f"**Патерн:** {pattern}" + (f" / {subtype}" if subtype else ""))
    lines.append("")
    lines.append(data.get("pattern_rationale", ""))
    lines.append("")
    return lines


def _render_what_if(data: dict) -> list[str]:
    lines = ["## Блок: Альтернативи (What-If)", ""]
    for alt in data.get("alternatives", []):
        lines.append(f"### {alt.get('title', '')}")
        lines.append(alt.get("premise", ""))
        lines.append("")
        for move in alt.get("moves", []):
            action = move.get("action", "")
            section = move.get("target_section", "")
            target = move.get("target", "")
            new_text = move.get("new_text")
            rationale = move.get("rationale", "")
            change = f"{target} -> {new_text}" if new_text else target
            lines.append(f"- **{action}** ({section}): {change} — {rationale}")
        lines.append("")
        lines.append(f"Очікуваний ефект: {alt.get('expected_impact', '')}")
        lines.append("")
    return lines


def _render_hypotheses(data: dict) -> list[str]:
    lines = ["## Блок: Гіпотези", ""]
    for h in data.get("hypotheses", []):
        lines.append(f"- **[{h.get('category', '')} / {h.get('quadrant', '')}]** {h.get('text', '')}")
    lines.append("")
    return lines


def _render_scenario(data: dict) -> list[str]:
    lines = ["## Блок: Сценарій використання", ""]
    persona = data.get("persona", {})
    lines.append(f"**Персона:** {persona.get('name', '')} — {persona.get('role', '')}")
    lines.append(f"Біль: {persona.get('pain_point', '')}")
    lines.append("")
    lines.append("**Часова шкала:**")
    for step in data.get("timeline", []):
        lines.append(f"- [{step.get('step_type', '')}] {step.get('text', '')}")
    lines.append("")
    metrics = data.get("metrics", {})
    before = metrics.get("before", {})
    after = metrics.get("after", {})
    lines.append(f"**До:** {before.get('value', '')} — {before.get('label', '')}")
    lines.append(f"**Після:** {after.get('value', '')} — {after.get('label', '')}")
    lines.append("")
    return lines


def _render_pitch(data: dict) -> list[str]:
    lines = ["## Блок: Презентація (Pitch)", ""]
    lines.append("**Для інвестора:**")
    for slide in data.get("investor", []):
        lines.append(f"- *{slide.get('type', '')}* — **{slide.get('headline', '')}**: {slide.get('content', '')}")
    lines.append("")
    lines.append("**Для клієнта:**")
    for slide in data.get("customer", []):
        lines.append(f"- *{slide.get('type', '')}* — **{slide.get('headline', '')}**: {slide.get('content', '')}")
    lines.append("")
    return lines


_RENDERERS = {
    "empathy_map": _render_empathy_map,
    "models_options": _render_models_options,
    "canvas": _render_canvas,
    "architecture": _render_architecture,
    "what_if": _render_what_if,
    "hypotheses": _render_hypotheses,
    "scenario": _render_scenario,
    "pitch": _render_pitch,
}

# Fixed presentation order — the domain chain's generation order
# (empathy_map -> ... -> pitch), not alphabetical, so the judge reads
# blocks in the order they build on each other.
BLOCK_ORDER: list[str] = [
    "empathy_map", "models_options", "canvas", "architecture",
    "what_if", "hypotheses", "scenario", "pitch",
]


def render_all_blocks_md(blocks: dict[str, Any]) -> str:
    lines: list[str] = []
    for block in BLOCK_ORDER:
        data = blocks.get(block)
        if data is None:
            continue
        lines.extend(_RENDERERS[block](data))
    return "\n".join(lines)
