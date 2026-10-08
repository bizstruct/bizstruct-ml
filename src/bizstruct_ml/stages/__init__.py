"""Stage generators: the stage-specific half of generation (prompt + conversion)."""

from bizstruct_domain.schemas import Stage

from bizstruct_ml.core.stage_runner import StageGenerator
from bizstruct_ml.stages.brief import BriefGenerator
from bizstruct_ml.stages.canvas import CanvasGenerator
from bizstruct_ml.stages.customer_scenario import CustomerScenarioGenerator
from bizstruct_ml.stages.empathy_map import EmpathyMapGenerator
from bizstruct_ml.stages.future_scenario import FutureScenarioGenerator
from bizstruct_ml.stages.ideation import IdeationGenerator
from bizstruct_ml.stages.patterns import PatternsGenerator
from bizstruct_ml.stages.pitch import PitchGenerator
from bizstruct_ml.stages.storytelling import StorytellingGenerator
from bizstruct_ml.stages.swot_errc_cycle import SwotErrcCycleGenerator

SLICE_1_GENERATORS: dict[Stage, StageGenerator] = {
    g.stage: g for g in (BriefGenerator(), EmpathyMapGenerator(), CustomerScenarioGenerator(), IdeationGenerator())
}

SLICE_2_GENERATORS: dict[Stage, StageGenerator] = {
    **SLICE_1_GENERATORS,
    **{g.stage: g for g in (PatternsGenerator(), CanvasGenerator())},
}

SLICE_3_GENERATORS: dict[Stage, StageGenerator] = {**SLICE_2_GENERATORS, Stage.SWOT_ERRC_CYCLE: SwotErrcCycleGenerator()}

SLICE_4_GENERATORS: dict[Stage, StageGenerator] = {
    **SLICE_3_GENERATORS,
    **{g.stage: g for g in (StorytellingGenerator(), FutureScenarioGenerator(), PitchGenerator())},
}
