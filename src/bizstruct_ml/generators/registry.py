from bizstruct_domain.chain import STAGES

from bizstruct_ml.generators.base import (
    ArchitectureGenerator,
    BaseGenerator,
    CanvasGenerator,
    EmpathyMapGenerator,
    HypothesesGenerator,
    ModelsOptionsGenerator,
    PitchGenerator,
    ScenarioGenerator,
    WhatIfGenerator,
)

GENERATORS: dict[str, BaseGenerator] = {
    "models_options": ModelsOptionsGenerator(),
    "canvas": CanvasGenerator(),
    "empathy_map": EmpathyMapGenerator(),
    "hypotheses": HypothesesGenerator(),
    "pitch": PitchGenerator(),
    "scenario": ScenarioGenerator(),
    "what_if": WhatIfGenerator(),
    "architecture": ArchitectureGenerator(),
}


def _validate_registry_against_stages() -> None:
    """Fail fast on startup if a registered generator has no matching stage.

    Every GENERATORS key must be a stage id in bizstruct_domain.chain.STAGES
    — no id-mapping layer. (There used to be a `canvas_data` -> `canvas`
    _STAGE_ID_OVERRIDES bridge here; the wire-level block id was renamed to
    `canvas` to match STAGES instead of growing that mapping further — see
    the canvas rename commit.) This deliberately does NOT go the other way
    — STAGES includes stages (`brief`, `value_map`, `environment_scan`,
    `assessment`, ...) that have no generator here yet, and that's expected
    in this pilot slice.
    """
    known_stage_ids = {s.id for s in STAGES}
    for block_id in GENERATORS:
        if block_id not in known_stage_ids:
            raise RuntimeError(
                f"generator registry configuration error: block '{block_id}' "
                "is not a known stage in bizstruct_domain.chain.STAGES"
            )


_validate_registry_against_stages()
