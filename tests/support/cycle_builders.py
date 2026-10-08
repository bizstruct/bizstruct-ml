"""Builders for swot_errc_cycle artifacts and rows in tests: a Swot with an exact score, canvases,
Errcs, and DONE rows holding them (ids derived like the generators derive them)."""

from bizstruct_domain.schemas import (
    THREAT_QUESTIONS_BY_CLUSTER,
    ArtifactRecord,
    ArtifactType,
    Canvas,
    CanvasCard,
    CanvasSections,
    ERRCActionType,
    Errc,
    ErrcMove,
    CanvasSection,
    Stage,
    StageRow,
    StageStatus,
    Swot,
    SwotAxisStatement,
    SwotGenerated,
    SwotCluster,
    SwotClusterResult,
    SwotOpportunity,
    SwotThreat,
    derive_artifact_id,
)
from pydantic import BaseModel


def swot_clusters(total: int) -> list[SwotClusterResult]:
    """Clusters whose weighted_weakness_threat_score is `total` (21..105: the fixed threat catalog rated 1..5;
    the axis statements are positive so they add nothing)."""
    extra = total - 21
    assert 0 <= extra <= 84, total
    clusters = []
    for kind in SwotCluster:
        threats = []
        for question in THREAT_QUESTIONS_BY_CLUSTER[kind]:
            bump = min(4, extra)
            extra -= bump
            threats.append(SwotThreat(question=question, text="threat", score=1 + bump))
        axes = [SwotAxisStatement(positive_statement="p", negative_statement="n", score=s, importance=5, certainty=5) for s in (1, 2)]
        clusters.append(SwotClusterResult(cluster=kind, axis_statements=axes, opportunities=[SwotOpportunity(text="o", score=3)], threats=threats))
    return clusters


def swot_generated(total: int) -> SwotGenerated:
    return SwotGenerated(clusters=swot_clusters(total))


def swot_scoring(total: int, row_id: str, version: int) -> Swot:
    """A valid Swot whose weighted_weakness_threat_score is `total`."""
    clusters = swot_clusters(total)
    swot = Swot(
        id=derive_artifact_id(row_id, ArtifactType.SWOT, version),
        canvas_id=derive_artifact_id(row_id if version > 1 else "row_canvas_0", ArtifactType.CANVAS, version),
        canvas_version=version,
        clusters=clusters,
    )
    assert swot.weighted_weakness_threat_score == total
    return swot


def canvas_model(canvas_id: str, version: int, texts: dict[str, list[str]] | None = None, previous: str | None = None) -> Canvas:
    sections = {}
    for section in CanvasSection:
        wanted = (texts or {}).get(section.value) or [f"{section.value} card {i}" for i in range(2)]
        sections[section.value] = [CanvasCard(id=f"{canvas_id}:{section.value}:{i}", text=t) for i, t in enumerate(wanted)]
    return Canvas(
        id=canvas_id, group_id="group_0", empathy_map_ids=["em_0"], version=version, previous_version_id=previous,
        sections=CanvasSections(**sections),
    )


def errc_model(row_id: str, version: int, canvas_id: str, swot_id: str, moves: list[ErrcMove] | None = None) -> Errc:
    return Errc(
        id=derive_artifact_id(row_id, ArtifactType.ERRC, version), canvas_id=canvas_id, swot_id=swot_id,
        from_version=version, to_version=version + 1,
        result_canvas_id=derive_artifact_id(row_id, ArtifactType.CANVAS, version + 1),
        moves=moves or [ErrcMove(action=ERRCActionType.CREATE, target_section=CanvasSection.CHANNELS, new_text="new", opposite_side_impact="i", rationale="r")],
    )


def done_row(row_id: str, stage: Stage, items: list[tuple[ArtifactType, BaseModel]], refs: dict[Stage, list[str]] | None = None) -> StageRow:
    return StageRow(
        id=row_id, stage=stage, status=StageStatus.DONE, attempt_id="a", refs=refs or {},
        artifacts=[ArtifactRecord(id=getattr(m, "id"), type=t, data=m.model_dump(mode="json")) for t, m in items],
    )


def finished_cycle(totals: tuple[int, ...], cycle_row_id: str = "row_cycle_0", canvas_row_id: str = "row_canvas_0"):
    """The canvas row (v1) and a DONE cycle row for a loop that produced one Swot per total, an Errc after every
    Swot but the last, and canvases 2..K. Returns (canvas_row, cycle_row, canvases, swots, errcs)."""
    k = len(totals)
    canvas_ids = [derive_artifact_id(canvas_row_id, ArtifactType.CANVAS, 1)] + [
        derive_artifact_id(cycle_row_id, ArtifactType.CANVAS, v) for v in range(2, k + 1)
    ]
    canvases = [canvas_model(cid, v, previous=canvas_ids[v - 2] if v > 1 else None) for v, cid in enumerate(canvas_ids, start=1)]
    swots = []
    for v, total in enumerate(totals, start=1):
        s = swot_scoring(total, cycle_row_id, v)
        swots.append(s.model_copy(update={"canvas_id": canvas_ids[v - 1]}))
    errcs = [errc_model(cycle_row_id, v, canvas_ids[v - 1], swots[v - 1].id) for v in range(1, k)]
    canvas_row = done_row(canvas_row_id, Stage.CANVAS, [(ArtifactType.CANVAS, canvases[0])])
    cycle_row = done_row(
        cycle_row_id, Stage.SWOT_ERRC_CYCLE,
        [*[(ArtifactType.SWOT, s) for s in swots], *[(ArtifactType.ERRC, e) for e in errcs], *[(ArtifactType.CANVAS, c) for c in canvases[1:]]],
        refs={Stage.CANVAS: [canvas_row_id]},
    )
    return canvas_row, cycle_row, canvases, swots, errcs
