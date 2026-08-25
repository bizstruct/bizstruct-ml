from bizstruct_domain.chain import STAGES

from bizstruct_ml.generators.base import (
    ArchitectureGenerator,
    BaseGenerator,
    CanvasDataGenerator,
    EmpathyMapGenerator,
    HypothesesGenerator,
    ModelsOptionsGenerator,
    PitchGenerator,
    ScenarioGenerator,
    WhatIfGenerator,
)

GENERATORS: dict[str, BaseGenerator] = {
    "models_options": ModelsOptionsGenerator(),
    "canvas_data": CanvasDataGenerator(),
    "empathy_map": EmpathyMapGenerator(),
    "hypotheses": HypothesesGenerator(),
    "pitch": PitchGenerator(),
    "scenario": ScenarioGenerator(),
    "what_if": WhatIfGenerator(),
    "architecture": ArchitectureGenerator(),
}

# bizstruct-ml's wire-level block ids (queue message `block`, hook payload,
# ProjectState field names) predate bizstruct_domain and don't all match its
# stage ids one-for-one. `canvas_data` here is `canvas` in STAGES; everything
# else lines up. This map exists solely to bridge that one naming drift for
# the startup check below — it does NOT rename the wire protocol, which is
# out of scope for this change (would break the backend/frontend contract).
_STAGE_ID_OVERRIDES: dict[str, str] = {
    "canvas_data": "canvas",
}


def _validate_registry_against_stages() -> None:
    """Fail fast on startup if a registered generator has no matching stage.

    Every GENERATORS key must resolve (directly, or via
    `_STAGE_ID_OVERRIDES`) to a stage id in `bizstruct_domain.chain.STAGES`.
    This deliberately does NOT go the other way — STAGES includes stages
    (`brief`, `value_map`, `environment_scan`, `assessment`, ...) that have
    no generator here yet, and that's expected in this pilot slice.
    """
    known_stage_ids = {s.id for s in STAGES}
    for block_id in GENERATORS:
        stage_id = _STAGE_ID_OVERRIDES.get(block_id, block_id)
        if stage_id not in known_stage_ids:
            raise RuntimeError(
                f"generator registry configuration error: block '{block_id}' "
                f"(resolved stage id '{stage_id}') is not a known stage in "
                "bizstruct_domain.chain.STAGES"
            )


_validate_registry_against_stages()
