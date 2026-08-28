"""Post-validation of generated block text for degeneration that Pydantic's
own schema (min_length/max_length/enums/cross-field validators) cannot
catch, because a degenerate string is still a syntactically valid one.

Empirically established (see experiments/README.md and the min_length
provocation test in experiments/min_length_probe.py): `min_length` in
structured output pressures *length*, not *content*. When a model can't
produce enough meaningful text, it pads with whatever satisfies the
character count — disallowed-script characters, mid-word breaks, or
repeated punctuation runs. None of this trips a Pydantic constraint or a
JSON Schema violation, so it reaches storage unless something else checks
for it.

Three violation kinds are retry-worthy (raise `DegenerateTextError`, which
`generators/base.py` adds to the same tenacity retry loop as
`ValidationError`/`LLMError`): `language_mismatch`, `disallowed_script`,
`repeated_sequence`. A fourth, `truncation_near_max_length`, is logged
only — it's the model legitimately running into a length ceiling, not
degenerating, and needs a schema fix (raising max_length), not a retry
that will just hit the same ceiling again.

Every violation found (retry-worthy or not) is returned so the caller can
attach it to the Langfuse span — see part C of the data-quality brief:
"без цього неможливо оцінити частоту дефекту в експериментальних даних".

Language check (part E follow-up): projects are single-language now (no
more `_uk`/`_en` field pairs — see bizstruct_domain's block modules), so
the expected language isn't inferred from a field-name suffix anymore. The
caller passes it in explicitly (`expected_language`, the same "uk"/"en"
value used to build the prompt — see generators/base.py), and every text
field in the block is checked against that one language uniformly.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

# ── thresholds — calibrated against experiments/results/ (4 models × 5
# ideas × 8 blocks each, back when fields were still _uk/_en pairs); see
# scripts/calibrate_degenerate_text.py and the task summary for the
# per-model violation counts these were tuned against.

# Fraction of *alphabetic* characters that must belong to the expected
# language's script for a text field not to be flagged. Below this,
# treated as language_mismatch. Deliberately loose — a term, brand name,
# or code identifier borrowed from the other language is normal and must
# not trip this; only fields substantially in the wrong script should.
_UK_MIN_CYRILLIC_RATIO = 0.55
_EN_MIN_LATIN_RATIO = 0.55
# Below this many alphabetic characters, the ratio is too noisy to judge
# (e.g. a 3-letter field) — skip the language check entirely.
_MIN_LETTERS_FOR_LANGUAGE_CHECK = 8

# `title` fields consistently mix a native descriptor with an English
# brand-style product name by design across this dataset (e.g. "Інституційна
# ліцензія · Campus SkillSprint") — calibration against experiments/results/
# found this pattern alone would trip the ratio check regardless of the
# project's language, with zero true positives. Every other field (prose:
# rationale, premise, description, summary, ...) is still checked.
_LANGUAGE_CHECK_EXEMPT_FIELDS = {"title"}

# Unicode ranges that must never appear in uk/en business content — the
# single most reliable degeneration signal observed (see brief).
_DISALLOWED_SCRIPT_RANGES: list[tuple[int, int]] = [
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Extension A
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
]

# A single character repeated this many times in a row, or a short (1-3
# char) group repeated this many times in a row.
_SINGLE_CHAR_REPEAT_THRESHOLD = 8
_SHORT_GROUP_REPEAT_THRESHOLD = 5
_REPEATED_SINGLE_CHAR_RE = re.compile(r"(.)\1{" + str(_SINGLE_CHAR_REPEAT_THRESHOLD - 1) + r",}")
_REPEATED_GROUP_RE = re.compile(r"(.{1,3})\1{" + str(_SHORT_GROUP_REPEAT_THRESHOLD - 1) + r",}")

# A field within this fraction of its max_length, ending mid-word (no
# sentence-ending punctuation as the last non-space character), is flagged
# as running into the length ceiling rather than degenerating.
_TRUNCATION_LENGTH_RATIO = 0.9
_SENTENCE_END_CHARS = set(".!?…»\")'")


@dataclass(frozen=True)
class TextViolation:
    field_path: str
    kind: str  # "language_mismatch" | "disallowed_script" | "repeated_sequence" | "truncation_near_max_length"
    detail: str
    retry_worthy: bool


class DegenerateTextError(Exception):
    """Raised when validate_block_text finds at least one retry-worthy
    violation. Carries the full violation list (including log-only ones)
    for the caller to attach to Langfuse regardless of which kind
    triggered the raise."""

    def __init__(self, violations: list[TextViolation]) -> None:
        self.violations = violations
        summary = "; ".join(f"{v.field_path}: {v.kind} ({v.detail})" for v in violations if v.retry_worthy)
        super().__init__(f"degenerate text detected: {summary}")


def _max_length_of(field_info: FieldInfo) -> int | None:
    for meta in field_info.metadata:
        max_length = getattr(meta, "max_length", None)
        if max_length is not None:
            return max_length
    return None


def _leaf_name(path: str) -> str:
    tail = path.rsplit(".", 1)[-1]
    return tail.split("[", 1)[0]


def _check_language(field_path: str, text: str, expected_language: str) -> TextViolation | None:
    name = _leaf_name(field_path)
    if name in _LANGUAGE_CHECK_EXEMPT_FIELDS:
        return None
    if expected_language not in ("uk", "en"):
        return None  # unknown language code — nothing to check against, not our call to guess

    letters = [c for c in text if c.isalpha()]
    if len(letters) < _MIN_LETTERS_FOR_LANGUAGE_CHECK:
        return None

    cyrillic = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
    ratio = (cyrillic if expected_language == "uk" else latin) / len(letters)
    threshold = _UK_MIN_CYRILLIC_RATIO if expected_language == "uk" else _EN_MIN_LATIN_RATIO

    if ratio < threshold:
        return TextViolation(
            field_path=field_path,
            kind="language_mismatch",
            detail=f"expected mostly {expected_language} script, got {ratio:.0%} (threshold {threshold:.0%})",
            retry_worthy=True,
        )
    return None


def _check_disallowed_scripts(field_path: str, text: str) -> TextViolation | None:
    offending = {c for c in text if any(lo <= ord(c) <= hi for lo, hi in _DISALLOWED_SCRIPT_RANGES)}
    if offending:
        return TextViolation(
            field_path=field_path,
            kind="disallowed_script",
            detail=f"contains characters outside uk/en scripts: {''.join(sorted(offending))[:20]!r}",
            retry_worthy=True,
        )
    return None


def _check_repeated_sequences(field_path: str, text: str) -> TextViolation | None:
    m = _REPEATED_SINGLE_CHAR_RE.search(text) or _REPEATED_GROUP_RE.search(text)
    if m:
        return TextViolation(
            field_path=field_path,
            kind="repeated_sequence",
            detail=f"{m.group(0)[:30]!r} repeated abnormally",
            retry_worthy=True,
        )
    return None


def _check_truncation(field_path: str, text: str, max_length: int | None) -> TextViolation | None:
    if max_length is None:
        return None
    stripped = text.rstrip()
    if not stripped:
        return None
    if len(text) < max_length * _TRUNCATION_LENGTH_RATIO:
        return None
    if stripped[-1] in _SENTENCE_END_CHARS:
        return None
    return TextViolation(
        field_path=field_path,
        kind="truncation_near_max_length",
        detail=f"len={len(text)} is {len(text) / max_length:.0%} of max_length={max_length}, "
        f"ends mid-word ({stripped[-15:]!r})",
        retry_worthy=False,
    )


def _check_str_field(
    field_path: str, text: str, field_info: FieldInfo | None, expected_language: str, out: list[TextViolation]
) -> None:
    language_violation = _check_language(field_path, text, expected_language)
    if language_violation is not None:
        out.append(language_violation)
    for check in (_check_disallowed_scripts, _check_repeated_sequences):
        violation = check(field_path, text)
        if violation is not None:
            out.append(violation)
    if field_info is not None:
        violation = _check_truncation(field_path, text, _max_length_of(field_info))
        if violation is not None:
            out.append(violation)


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _walk_field(
    annotation: Any, value: Any, path: str, field_info: FieldInfo | None, expected_language: str,
    out: list[TextViolation],
) -> None:
    if value is None:
        return
    annotation = _unwrap_optional(annotation)

    if annotation is str:
        if isinstance(value, str):
            _check_str_field(path, value, field_info, expected_language, out)
        return

    origin = get_origin(annotation)
    if origin in (list, tuple) and isinstance(value, (list, tuple)):
        args = get_args(annotation)
        item_type = args[0] if args else None
        for i, item in enumerate(value):
            _walk_field(item_type, item, f"{path}[{i}]", None, expected_language, out)
        return

    if inspect.isclass(annotation) and issubclass(annotation, BaseModel) and isinstance(value, dict):
        _walk_model(annotation, value, path, expected_language, out)
        return
    # Anything else (int, bool, enum, UUID, dict[str, str], ...) is not a
    # free-text field this validator concerns itself with.


def _walk_model(
    model_cls: type[BaseModel], data: dict, path: str, expected_language: str, out: list[TextViolation]
) -> None:
    for name, field_info in model_cls.model_fields.items():
        if name not in data:
            continue
        child_path = f"{path}.{name}" if path else name
        _walk_field(field_info.annotation, data[name], child_path, field_info, expected_language, out)


def validate_block_text(schema: type[BaseModel], data: dict, expected_language: str) -> list[TextViolation]:
    """Walks `data` against `schema`'s field structure (recursing into
    nested models and lists) and returns every violation found — both
    retry-worthy and log-only. Does not raise; callers decide what to do
    (see generators/base.py). `expected_language` is the same "uk"/"en"
    value the prompt was built with (see llm/prompts/*.py's `lang`)."""
    violations: list[TextViolation] = []
    _walk_model(schema, data, "", expected_language, violations)
    return violations
