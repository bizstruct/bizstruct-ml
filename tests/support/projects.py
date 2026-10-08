"""Scripted projects for slice 2 tests: segments with known features, the four shapes the
brief asks for, and a scripted generator LLM that answers every stage."""

import json
from dataclasses import dataclass

from bizstruct_domain.schemas import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    CanvasCardDraft,
    CanvasGenerated,
    CanvasSectionsGenerated,
    CustomerScenarioGenerated,
    Epicenter,
    EmpathyMapGenerated,
    EpicenterClassification,
    IdeationGenerated,
    Pattern,
    PatternsGenerated,
    PatternTag,
    ERRCActionType,
    ErrcGenerated,
    ErrcMove,
    CanvasSection,
    PricingTier,
    SegmentRelationType,
    SwotGenerated,
    Stage,
    StageStatus,
    derive_artifact_id,
)
from bizstruct_domain.schemas.pattern import CanvasGroupGenerated, PairwiseSegmentScoreGenerated, SegmentPairGenerated

from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from tests.support.fake_backend import FakeBackend
from tests.support.fakes import FakeLLM, brief_model, empathy_generated

NO_FINDINGS = json.dumps({"score": 5, "violations": []})


@dataclass(frozen=True)
class Seg:
    candidate: str
    channel: str = "digital-self-service"
    relationship: str = "self-service"
    tier: PricingTier | None = PricingTier.MID_MARKET
    signal: bool = False
    epicenters: tuple[Epicenter, ...] = (Epicenter.CUSTOMER_DRIVEN,)

    @property
    def persona(self) -> str:
        return f"Persona of {self.candidate}"


def pair(a: int, b: int, synergy: int, conflict: int) -> PairwiseSegmentScoreGenerated:
    return PairwiseSegmentScoreGenerated(
        segment_pair=SegmentPairGenerated(segment_alias_a=f"S{a}", segment_alias_b=f"S{b}"), synergy=synergy, conflict=conflict
    )


def group(*numbers: int, relation: SegmentRelationType = SegmentRelationType.SEGMENTED) -> CanvasGroupGenerated:
    return CanvasGroupGenerated(segment_aliases=[f"S{n}" for n in numbers], relation_type=relation)


def tag(pattern: Pattern, rationale: str = "Grounded in the epicenter of the segments.", subtype=None) -> PatternTag:
    return PatternTag(pattern=pattern, subtype=subtype, rationale=rationale)


@dataclass(frozen=True)
class Shape:
    name: str
    segments: tuple[Seg, ...]
    patterns: PatternsGenerated
    # the expected canvases: the real segment numbers (1-based) of each group, in order
    groups: tuple[tuple[int, ...], ...]


ONE = Shape(
    "one segment",
    (Seg("Urban parents"),),
    PatternsGenerated(pairwise_scores=[], groups=[group(1)], pattern_tags=[]),
    ((1,),),
)

THREE_IN_ONE_MULTI_SIDED = Shape(
    "three segments, one multi-sided group",
    (
        Seg("Event hosts", signal=True),
        Seg("Venue owners", signal=True, epicenters=(Epicenter.RESOURCE_DRIVEN,)),
        Seg("Sponsors", signal=False, epicenters=(Epicenter.FINANCE_DRIVEN,)),
    ),
    PatternsGenerated(
        pairwise_scores=[pair(1, 2, 4, 0), pair(1, 3, 3, 0), pair(2, 3, 3, -1)],
        groups=[group(1, 2, 3, relation=SegmentRelationType.MULTI_SIDED)],
        pattern_tags=[tag(Pattern.MULTI_SIDED_PLATFORM)],
    ),
    ((1, 2, 3),),
)

SPLIT_IN_TWO = Shape(
    "two canvases",
    (
        Seg("Home cooks"),
        Seg("Hobby gardeners", channel="physical"),
        Seg("Industrial buyers", tier=PricingTier.LOW_COST, relationship="automated"),
    ),
    PatternsGenerated(
        pairwise_scores=[pair(1, 2, 3, 0), pair(1, 3, 1, -4), pair(2, 3, 0, -2)],
        groups=[group(1, 2), group(3)],
        pattern_tags=[],
    ),
    ((1, 2), (3,)),
)

SPLIT_IN_THREE = Shape(
    "three canvases",
    (Seg("Home cooks"), Seg("Fleet operators", tier=PricingTier.LOW_COST), Seg("Luxury hotels", tier=PricingTier.PREMIUM)),
    PatternsGenerated(
        pairwise_scores=[pair(1, 2, 1, -4), pair(1, 3, 0, -3), pair(2, 3, 1, -3)],
        groups=[group(1), group(2), group(3)],
        pattern_tags=[],
    ),
    ((1,), (2,), (3,)),
)

def multi_sided_claim_without_signal() -> Shape:
    """The model tags a multi-sided group although no scenario carries an interdependence signal."""
    segments = tuple(Seg(s.candidate, signal=False, epicenters=s.epicenters) for s in THREE_IN_ONE_MULTI_SIDED.segments)
    return Shape("multi-sided claim without any signal", segments, THREE_IN_ONE_MULTI_SIDED.patterns, ((1, 2, 3),))


SHAPES = (ONE, THREE_IN_ONE_MULTI_SIDED, SPLIT_IN_TWO, SPLIT_IN_THREE)


def canvas_generated(tag_: str = "") -> CanvasGenerated:
    def cards(section: str) -> list[CanvasCardDraft]:
        return [CanvasCardDraft(text=f"{section} card {n}{tag_}") for n in (1, 2)]

    return CanvasGenerated(sections=CanvasSectionsGenerated(**{name: cards(name) for name in CanvasSectionsGenerated.model_fields}))


def scenario_of(seg: Seg) -> CustomerScenarioGenerated:
    return CustomerScenarioGenerated(
        situation_narrative=f"{seg.persona} meets the offer on a weekday evening.",
        pricing_tier=seg.tier,
        channel_type=seg.channel,
        relationship_type=seg.relationship,
        interdependence_signal=seg.signal,
        open_questions=[f"Which channel fits {seg.candidate}?"],
    )


def ideation_of(seg: Seg) -> IdeationGenerated:
    return IdeationGenerated(
        epicenter=EpicenterClassification(
            tags=list(seg.epicenters) + ([Epicenter.MULTIPLE_EPICENTER] if len(seg.epicenters) > 1 else []),
            rationale=f"Signals of {seg.candidate}.",
        ),
        what_if_questions=[f"What if {seg.candidate} paid nothing?"],
    )


def default_moves(version: int) -> ErrcGenerated:
    """A raise of one existing card (its text gets a level suffix per iteration) and one new card; valid on every canvas version."""
    base = "value_propositions card 1"
    target = base if version == 1 else f"{base} (level {version - 1})"
    return ErrcGenerated(moves=[
        ErrcMove(action=ERRCActionType.RAISE, target_section=CanvasSection.VALUE_PROPOSITIONS, target_card_text=target,
                 new_text=f"{base} (level {version})", opposite_side_impact="costs rise a little", rationale="a strength"),
        ErrcMove(action=ERRCActionType.CREATE, target_section=CanvasSection.CHANNELS, new_text=f"new channel idea {version}",
                 opposite_side_impact="needs a partner", rationale="an opportunity"),
    ])


def scripted_llm(shape: Shape, *, patterns: PatternsGenerated | None = None, canvas=None, scores=None, errc=None) -> FakeLLM:
    """`scores`: the weighted score of the Swot of canvas version k is scores[k - 1] (the version is read off the
    prompt, so a retry gets the same answer). `errc(version, messages)` returns the ErrcGenerated of that step."""
    """Answers every stage by schema; the persona echoed in the prompt says which segment it is."""
    by_persona = {s.persona: s for s in shape.segments}

    def persona_in(user: str) -> Seg:
        return next(seg for name, seg in by_persona.items() if name in user)

    def reply(messages: list[dict], schema: type):
        user = messages[-1]["content"] if schema is not PatternsGenerated else messages[1]["content"]
        if schema is Brief:
            return brief_model().model_copy(update={"customer_segment_candidates": [s.candidate for s in shape.segments]})
        if schema is EmpathyMapGenerated:
            seg = next(s for s in shape.segments if f"for this segment: {s.candidate}" in user)
            return empathy_generated(seg.persona)
        if schema is CustomerScenarioGenerated:
            return scenario_of(persona_in(user))
        if schema is IdeationGenerated:
            return ideation_of(persona_in(user))
        if schema is PatternsGenerated:
            return patterns or shape.patterns
        if schema is CanvasGenerated:
            return canvas(messages, schema) if canvas else canvas_generated()
        if schema is SwotGenerated:
            from tests.support.cycle_builders import swot_generated

            return swot_generated(scores[canvas_version(messages) - 1])
        if schema is ErrcGenerated:
            version = canvas_version(messages)
            return errc(version, messages) if errc else default_moves(version)
        raise AssertionError(f"unexpected schema {schema}")

    return FakeLLM([reply])


def canvas_version(messages: list[dict]) -> int:
    import re

    return int(re.search(r"^Canvas version (\d+):", messages[1]["content"], re.M).group(1))


def stage_runner(llm: FakeLLM, judge_model: FakeJudgeModel | None = None, **kwargs) -> StageRunner:
    from bizstruct_ml.stages import SLICE_3_GENERATORS

    return StageRunner(
        SLICE_3_GENERATORS, llm, ConsistencyJudge(judge_model or FakeJudgeModel([NO_FINDINGS]), retry_wait=0), retry_wait=0, **kwargs
    )


def finish(backend: FakeBackend, row_id: str, artifacts: list[tuple[ArtifactType, object]]) -> None:
    """Mark an upstream row DONE with the given artifacts, as if it had run, and let be unfold the graph."""
    row = backend.rows[row_id]
    row.status = StageStatus.DONE
    row.attempt_id = row.attempt_id or "done"
    row.artifacts = [
        ArtifactRecord(id=getattr(m, "id", None) or derive_artifact_id(row_id, t, 0), type=t, data=m.model_dump(mode="json"))
        for t, m in artifacts
    ]
    backend.expand()


def seed(shape: Shape, *, through=Stage.PATTERNS, language: str = "en", dispatch: bool = True) -> FakeBackend:
    """A fake backend whose upstream rows (brief, maps, scenarios, ideations) are DONE with the shape's
    artifacts; the patterns row is PENDING (or RUNNING when `dispatch`) and canvas rows do not exist yet."""
    from bizstruct_domain.schemas import CustomerScenario, EmpathyMap, Ideation

    backend = FakeBackend(language=language, through=through)
    brief = brief_model().model_copy(update={"customer_segment_candidates": [s.candidate for s in shape.segments]})
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief)])
    for k, seg in enumerate(shape.segments):
        row_id = f"row_empathy_map_{k}"
        em = EmpathyMap.from_generated(
            empathy_generated(seg.persona), id=derive_artifact_id(row_id, ArtifactType.EMPATHY_MAP, 0), project_id="project_001"
        )
        finish(backend, row_id, [(ArtifactType.EMPATHY_MAP, em)])
        cs = CustomerScenario.from_generated(
            scenario_of(seg), id=derive_artifact_id(f"row_customer_scenario_{k}", ArtifactType.CUSTOMER_SCENARIO, 0), empathy_map_id=em.id
        )
        finish(backend, f"row_customer_scenario_{k}", [(ArtifactType.CUSTOMER_SCENARIO, cs)])
        ideation = Ideation.from_generated(
            ideation_of(seg), id=derive_artifact_id(f"row_ideation_{k}", ArtifactType.IDEATION, 0), empathy_map_id=em.id
        )
        finish(backend, f"row_ideation_{k}", [(ArtifactType.IDEATION, ideation)])
    if dispatch:
        backend.dispatch_ready()
    return backend
