"""Generator-level coverage for the `architecture` block on bizstruct_domain."""
from unittest.mock import AsyncMock, patch

import pytest
from bizstruct_domain.blocks.architecture import Architecture
from pydantic import ValidationError

from bizstruct_ml.generators.base import ArchitectureGenerator
from bizstruct_ml.schemas.project import ProjectState

RATIONALE = "A rationale long enough in English to satisfy the field's minimum length validation."


def _project() -> ProjectState:
    return ProjectState(
        id="00000000-0000-0000-0000-000000000001",
        title="EcoSync",
        idea="Automate ESG reporting for mid-market companies.",
        status="in_progress",
    )


def _valid_payload(**overrides) -> dict:
    payload = dict(
        epicenter="customer_driven",
        epicenter_rationale=RATIONALE,
        pattern="free",
        pattern_subtype="freemium",
        pattern_rationale=RATIONALE,
    )
    payload.update(overrides)
    return payload


async def test_generator_accepts_valid_llm_output():
    generator = ArchitectureGenerator()
    parsed = Architecture(**_valid_payload())
    with patch(
        "bizstruct_ml.llm.client.LLMClient.generate_structured",
        AsyncMock(return_value=parsed),
    ):
        result = await generator.generate(_project())
    assert result["epicenter"] == "customer_driven"
    assert result["pattern"] == "free"
    assert result["pattern_subtype"] == "freemium"


def test_old_epicenter_value_rejected():
    # "Competitor-driven" existed in the old local schema but was never a
    # real Osterwalder & Pigneur epicenter — bizstruct_domain doesn't have it.
    with pytest.raises(ValidationError):
        Architecture(**_valid_payload(epicenter="Competitor-driven"))


def test_old_pattern_value_rejected():
    # "PAID" was an invented value in the old local schema.
    with pytest.raises(ValidationError):
        Architecture(**_valid_payload(pattern="PAID", pattern_subtype=None))


def test_free_without_subtype_rejected():
    with pytest.raises(ValidationError):
        Architecture(**_valid_payload(pattern="free", pattern_subtype=None))


def test_free_with_freemium_accepted():
    model = Architecture(**_valid_payload(pattern="free", pattern_subtype="freemium"))
    assert model.pattern_subtype.value == "freemium"


async def test_generator_retries_on_validation_error_from_llm(monkeypatch):
    """Cross-field validator failures (e.g. missing required subtype) must retry."""
    generator = ArchitectureGenerator()
    good = Architecture(**_valid_payload())

    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # simulate the LLM client itself raising on a bad parse
            raise ValidationError.from_exception_data(
                title="Architecture",
                line_errors=[{
                    "type": "value_error",
                    "loc": ("pattern_subtype",),
                    "msg": "pattern requires a subtype",
                    "input": None,
                    "ctx": {"error": ValueError("pattern requires a subtype")},
                }],
            )
        return good

    with patch("bizstruct_ml.llm.client.LLMClient.generate_structured", flaky):
        result = await generator.generate(_project())

    assert calls["n"] == 2
    assert result["epicenter"] == "customer_driven"
