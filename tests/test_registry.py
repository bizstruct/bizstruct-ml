"""Startup validation: every generator in the registry must map to a known stage."""
from bizstruct_domain.chain import STAGES

from bizstruct_ml.generators.registry import GENERATORS, _validate_registry_against_stages


def test_registry_validates_cleanly_against_current_code():
    # Already ran at import time; re-running must be a no-op (idempotent, no raise).
    _validate_registry_against_stages()


def test_every_generator_resolves_to_a_known_stage():
    known_stage_ids = {s.id for s in STAGES}
    for block_id in GENERATORS:
        assert block_id in known_stage_ids, (
            f"generator '{block_id}' does not exist in bizstruct_domain.chain.STAGES"
        )


def test_validation_raises_on_unknown_block(monkeypatch):
    monkeypatch.setitem(GENERATORS, "not_a_real_stage", GENERATORS["architecture"])
    try:
        try:
            _validate_registry_against_stages()
            assert False, "expected RuntimeError for an unregistered stage id"
        except RuntimeError as e:
            assert "not_a_real_stage" in str(e)
    finally:
        del GENERATORS["not_a_real_stage"]
