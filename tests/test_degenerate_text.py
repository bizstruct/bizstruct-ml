"""Unit tests for validation/degenerate_text.py — thresholds calibrated
against experiments/results/ (see scripts/calibrate_degenerate_text.py and
the task summary for per-model counts this was tuned against). Fields are
single-language (part E — no more _uk/_en pairs); expected_language is
passed in explicitly, the same way generators/base.py does it."""

from pydantic import BaseModel, Field

from bizstruct_ml.validation.degenerate_text import DegenerateTextError, validate_block_text


class _Item(BaseModel):
    title: str = Field(default="")
    rationale: str = Field(default="", max_length=60)


class _Block(BaseModel):
    items: list[_Item] = Field(default_factory=list)
    summary: str = Field(default="")


def _kinds(violations) -> set[str]:
    return {v.kind for v in violations}


def test_clean_text_produces_no_violations_uk():
    data = {
        "items": [
            {
                "title": "Заголовок",
                "rationale": "Достатньо довге обґрунтування українською мовою тут.",
            }
        ],
        "summary": "Короткий підсумок написаний українською мовою повністю.",
    }
    violations = validate_block_text(_Block, data, "uk")
    assert violations == []


def test_clean_text_produces_no_violations_en():
    data = {
        "items": [{"title": "Title", "rationale": "A sufficiently long rationale written in English here."}],
        "summary": "A short summary written entirely in English.",
    }
    violations = validate_block_text(_Block, data, "en")
    assert violations == []


def test_title_field_exempt_from_language_check():
    # Deliberate brand-name mixing convention, confirmed in real generation
    # output (e.g. "Інституційна ліцензія · Campus SkillSprint") — must not
    # be flagged as language_mismatch, regardless of project language.
    data = {"items": [{"title": "Платформа · Campus SkillSprint", "rationale": ""}]}
    violations = validate_block_text(_Block, data, "uk")
    assert "language_mismatch" not in _kinds(violations)


def test_language_mismatch_detected_when_field_is_wrong_language():
    data = {"items": [{"rationale": "This entire field is written in English despite the project being Ukrainian."}]}
    violations = validate_block_text(_Block, data, "uk")
    assert any(v.kind == "language_mismatch" and v.field_path == "items[0].rationale" for v in violations)


def test_no_mismatch_when_field_matches_expected_language():
    data = {"items": [{"rationale": "This entire field is written in English, matching the project's language."}]}
    violations = validate_block_text(_Block, data, "en")
    assert "language_mismatch" not in _kinds(violations)


def test_short_field_below_letter_threshold_skips_language_check():
    data = {"items": [{"rationale": "ok"}]}
    violations = validate_block_text(_Block, data, "uk")
    assert "language_mismatch" not in _kinds(violations)


def test_unknown_language_code_skips_language_check():
    data = {"items": [{"rationale": "This entire field is written in English despite the project language."}]}
    violations = validate_block_text(_Block, data, "fr")
    assert "language_mismatch" not in _kinds(violations)


def test_disallowed_script_detected():
    data = {"items": [{"rationale": "Речення обривається ієрогліфом 訪 посеред тексту тут."}]}
    violations = validate_block_text(_Block, data, "uk")
    matches = [v for v in violations if v.kind == "disallowed_script"]
    assert len(matches) == 1
    assert matches[0].retry_worthy is True


def test_repeated_single_char_detected():
    data = {"summary": "ok" + "}" * 12}
    violations = validate_block_text(_Block, data, "en")
    assert any(v.kind == "repeated_sequence" for v in violations)


def test_repeated_short_group_detected():
    data = {"summary": "ok" + "}]" * 8}
    violations = validate_block_text(_Block, data, "en")
    assert any(v.kind == "repeated_sequence" for v in violations)


def test_truncation_near_max_length_is_log_only_not_retry_worthy():
    # rationale has max_length=60 in _Item
    data = {"items": [{"rationale": "a" * 58 + " end"}]}  # ends with a letter, no terminal punctuation
    violations = validate_block_text(_Block, data, "en")
    truncation = [v for v in violations if v.kind == "truncation_near_max_length"]
    assert len(truncation) == 1
    assert truncation[0].retry_worthy is False


def test_truncation_not_flagged_when_field_ends_with_sentence_punctuation():
    data = {"items": [{"rationale": "a" * 55 + " end."}]}
    violations = validate_block_text(_Block, data, "en")
    assert "truncation_near_max_length" not in _kinds(violations)


def test_truncation_not_flagged_when_well_under_max_length():
    data = {"items": [{"rationale": "A short rationale well under the limit"}]}
    violations = validate_block_text(_Block, data, "en")
    assert "truncation_near_max_length" not in _kinds(violations)


def test_degenerate_text_error_message_lists_only_retry_worthy():
    from bizstruct_ml.validation.degenerate_text import TextViolation

    violations = [
        TextViolation("a", "disallowed_script", "detail1", retry_worthy=True),
        TextViolation("b", "truncation_near_max_length", "detail2", retry_worthy=False),
    ]
    err = DegenerateTextError(violations)
    assert "a" in str(err)
    assert "b" not in str(err)
    assert err.violations == violations
