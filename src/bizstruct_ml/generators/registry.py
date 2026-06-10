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
