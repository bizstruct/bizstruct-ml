"""The swot_errc_cycle generator: the Canvas -> SWOT -> ERRC loop of one canvas, inside one message.

Starting from canvas v1 (held by the canvas row):
1. SWOT of version k; stop when `loop_should_continue(scores)` says so;
2. ERRC from version k; canvas k + 1 is built from canvas k and the moves, deterministically (`errc_apply`);
3. continue with k + 1.
Returned: Swot 1..K, Errc 1..K-1, canvases 2..K. The final version is NOT stored anywhere: the domain derives
it (`select_final_version` / `final_canvas`); it goes only into the trace metadata, with the score series.
"""

from typing import ClassVar

from bizstruct_domain.schemas import (
    ArtifactType,
    Canvas,
    Errc,
    ErrcGenerated,
    Stage,
    Swot,
    SwotGenerated,
    derive_artifact_id,
    loop_should_continue,
    select_final_version,
)
from pydantic import BaseModel

from bizstruct_ml.core.context import ContextError
from bizstruct_ml.core.stage_runner import GenerationFailed, LoopGenerator, LoopServices, StageContext
from bizstruct_ml.llm.prompts import errc as errc_prompt
from bizstruct_ml.llm.prompts import swot as swot_prompt
from bizstruct_ml.observability import tracing
from bizstruct_ml.stages.errc_apply import apply_moves


def start_canvas(ctx: StageContext) -> Canvas:
    canvases = [c for c in ctx.artifacts.get(Stage.CANVAS, []) if isinstance(c, Canvas)]
    if len(canvases) != 1 or canvases[0].version != 1:
        raise ContextError(f"cycle row {ctx.row.id} needs exactly one canvas v1 among its refs, got {[getattr(c, 'version', '?') for c in canvases]}")
    return canvases[0]


def check_contiguous(swots: list[Swot]) -> None:
    """The domain's `final_swot` raises on a gap in the Swot versions; fail here, before anything is returned."""
    found = [s.canvas_version for s in swots]
    if found != list(range(1, len(swots) + 1)):
        raise GenerationFailed(f"Swot versions must be contiguous from 1, got {found}")


class SwotErrcCycleGenerator(LoopGenerator):
    stage: ClassVar[Stage] = Stage.SWOT_ERRC_CYCLE
    contracts: ClassVar[tuple[type, ...]] = (SwotGenerated, ErrcGenerated)
    prompt_version: ClassVar[str] = f"swot={swot_prompt.PROMPT_VERSION},errc={errc_prompt.PROMPT_VERSION}"

    async def run_loop(self, ctx: StageContext, services: LoopServices) -> list[tuple[ArtifactType, BaseModel]]:
        row = ctx.row
        canvas = start_canvas(ctx)
        swots: list[Swot] = []
        errcs: list[Errc] = []
        canvases: list[Canvas] = [canvas]
        scores: list[float] = []
        version = 1
        while True:
            try:
                swot = await services.call(
                    SwotGenerated,
                    swot_prompt.build_messages(ctx, canvas),
                    self._swot_converter(row.id, canvas, version),
                    label=f"swot v{version}",
                )
                swots.append(swot)
                scores.append(swot.weighted_weakness_threat_score)
                if not loop_should_continue(scores):
                    break
                pair = await services.call_checked(
                    ErrcGenerated,
                    errc_prompt.build_messages(ctx, canvas, swot),
                    self._errc_converter(row.id, canvas, swot, version),
                    label=f"errc v{version}",
                    artifacts_of=lambda p, s=tuple(swots), e=tuple(errcs), c=tuple(canvases[1:]): [*s, *e, *c, p[0], p[1]],
                )
            except Exception as e:  # LLMError, DegenerateTextError, ValueError, GenerationFailed: name the iteration
                raise GenerationFailed(f"cycle iteration {version}: {e}") from e
            errcs.append(pair[0])
            canvas = pair[1]
            canvases.append(canvas)
            version += 1

        check_contiguous(swots)
        final = select_final_version(scores)
        with tracing.span("cycle_summary") as span:
            span.update(metadata={"final_version": final, "scores": scores, "iterations": len(swots)}, output={"final_version": final})
        return [
            *[(ArtifactType.SWOT, s) for s in swots],
            *[(ArtifactType.ERRC, e) for e in errcs],
            *[(ArtifactType.CANVAS, c) for c in canvases[1:]],
        ]

    @staticmethod
    def _swot_converter(row_id: str, canvas: Canvas, version: int):
        def convert(generated: BaseModel) -> Swot:
            return Swot.from_generated(
                generated,
                id=derive_artifact_id(row_id, ArtifactType.SWOT, version),
                canvas_id=canvas.id,
                canvas_version=version,
                environment_scan_id=None,
            )

        return convert

    @staticmethod
    def _errc_converter(row_id: str, canvas: Canvas, swot: Swot, version: int):
        def convert(generated: BaseModel) -> tuple[Errc, Canvas]:
            next_id = derive_artifact_id(row_id, ArtifactType.CANVAS, version + 1)
            errc = Errc.from_generated(
                generated,
                id=derive_artifact_id(row_id, ArtifactType.ERRC, version),
                swot_id=swot.id,
                canvas_id=canvas.id,
                from_version=version,
                to_version=version + 1,
                result_canvas_id=next_id,
            )
            return errc, apply_moves(canvas, errc, next_id)  # a move that matches no card is a ValueError: the call retries

        return convert
