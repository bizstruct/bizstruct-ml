"""Pieces shared by the stage prompts.

The field guide is rendered from the generation contract's JSON Schema, so the
descriptions the model reads are the domain's own and cannot drift from them.
"""

import json
from typing import Any

from pydantic import BaseModel

_LANGUAGES = {"uk": "Ukrainian", "en": "English"}

# Fields the system owns; the generator never sees them in context.
_SYSTEM_FIELDS = {"id", "project_id", "empathy_map_id"}


def language_name(code: str) -> str:
    return _LANGUAGES.get(code, code)


def language_rule(code: str) -> str:
    return (
        f"Write every free-text value in {language_name(code)}. "
        "Keep JSON keys and enum values exactly as the schema defines them."
    )


def content_json(model: BaseModel) -> str:
    """An artifact's content as JSON, without the system-owned id fields."""
    return json.dumps(
        model.model_dump(mode="json", exclude=_SYSTEM_FIELDS), ensure_ascii=False, indent=2
    )


def _resolve(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    return {**defs[ref.rsplit("/", 1)[-1]], **{k: v for k, v in schema.items() if k != "$ref"}} if ref else schema


def _type_label(schema: dict[str, Any], defs: dict[str, Any]) -> str:
    schema = _resolve(schema, defs)
    if "enum" in schema:
        return "one of " + ", ".join(f'"{v}"' for v in schema["enum"])
    if "anyOf" in schema:
        parts = [_type_label(s, defs) for s in schema["anyOf"] if s.get("type") != "null"]
        return " or ".join(parts) + (" or null" if any(s.get("type") == "null" for s in schema["anyOf"]) else "")
    kind = schema.get("type", "object")
    if kind == "array":
        bounds = [f"{k} {schema[key]}" for k, key in (("min", "minItems"), ("max", "maxItems")) if key in schema]
        inner = _type_label(schema.get("items", {}), defs)
        return f"list of {inner}" + (f" ({', '.join(bounds)} items)" if bounds else "")
    return kind


def _walk(schema: dict[str, Any], defs: dict[str, Any], prefix: str, lines: list[str]) -> None:
    schema = _resolve(schema, defs)
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        resolved = _resolve(prop, defs)
        description = prop.get("description") or resolved.get("description", "")
        optional = "" if name in required else ", optional"
        lines.append(f"- {prefix}{name} ({_type_label(prop, defs)}{optional}): {description}")
        if resolved.get("type") == "object":
            _walk(resolved, defs, f"{prefix}{name}.", lines)


def field_guide(contract: type[BaseModel]) -> str:
    """One line per field (nested objects expanded) from the contract's JSON Schema."""
    schema = contract.model_json_schema()
    lines: list[str] = []
    _walk(schema, schema.get("$defs", {}), "", lines)
    return "\n".join(lines)
