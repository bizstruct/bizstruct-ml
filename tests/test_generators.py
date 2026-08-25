"""Postprocessing invariants — tested without LLM calls."""
import pytest
from uuid import UUID
from pydantic import ValidationError

from bizstruct_ml.generators.base import (
    _postprocess_models_options,
    _postprocess_canvas_data,
    _postprocess_hypotheses,
    _postprocess_what_if,
    _postprocess_pitch,
)
from bizstruct_ml.schemas.blocks.models_options import ModelsOptions, BusinessModel
from bizstruct_ml.schemas.blocks.canvas_data import CanvasData, CanvasItem
from bizstruct_ml.schemas.blocks.hypotheses import Hypotheses, Hypothesis
from bizstruct_ml.schemas.blocks.what_if import WhatIf, WhatIfScenario
from bizstruct_ml.schemas.blocks.pitch import Pitch, PitchLocale, InvestorSlide, ClientSlide
from uuid import uuid4


def _make_model(monetization: str, score: int = 80) -> BusinessModel:
    return BusinessModel(
        id=uuid4(),
        name=f"Model {monetization}",
        tagline="tagline",
        description="desc",
        monetization=monetization,  # type: ignore[arg-type]
        target_segment="mid-market",
        key_metric="MRR",
        time_to_value="30 min",
        score=score,
    )


def test_models_options_order_guaranteed():
    # Input is in wrong order: retainer_plus_saas, subscription, transaction_fee
    data = ModelsOptions(
        models=[
            _make_model("retainer_plus_saas"),
            _make_model("subscription"),
            _make_model("transaction_fee"),
        ],
        selected_id=None,
    )
    result = _postprocess_models_options(data)
    order = [m["monetization"] for m in result["models"]]
    assert order == ["subscription", "transaction_fee", "retainer_plus_saas"]


def test_models_options_selected_id_nulled():
    existing_id = uuid4()
    data = ModelsOptions(
        models=[
            _make_model("subscription"),
            _make_model("transaction_fee"),
            _make_model("retainer_plus_saas"),
        ],
        selected_id=existing_id,
    )
    result = _postprocess_models_options(data)
    assert result["selected_id"] is None


def test_models_options_uuids_regenerated():
    original_ids = [uuid4() for _ in range(3)]
    data = ModelsOptions(
        models=[
            _make_model("subscription"),
            _make_model("transaction_fee"),
            _make_model("retainer_plus_saas"),
        ],
    )
    for m, oid in zip(data.models, original_ids):
        object.__setattr__(m, "id", oid)
    result = _postprocess_models_options(data)
    result_ids = [m["id"] for m in result["models"]]
    assert all(rid not in [str(oid) for oid in original_ids] for rid in result_ids)


def _make_canvas_item(text: str) -> CanvasItem:
    return CanvasItem(id=uuid4(), text=text, is_ai_generated=False)


def test_canvas_data_uuids_regenerated():
    original_id = uuid4()
    item = CanvasItem(id=original_id, text="test", is_ai_generated=False)
    data = CanvasData(
        key_partners=[item, item],
        key_activities=[item, item],
        key_resources=[item, item],
        value_propositions=[item, item],
        customer_relationships=[item, item],
        channels=[item, item],
        customer_segments=[item, item],
        cost_structure=[item, item],
        revenue_streams=[item, item],
    )
    result = _postprocess_canvas_data(data)
    for items in result.values():
        for it in items:
            assert it["id"] != str(original_id)
            assert it["is_ai_generated"] is True


def test_hypotheses_missing_category_raises():
    # Schema validator catches missing category at construction time.
    with pytest.raises(ValidationError):
        Hypotheses(hypotheses=[
            Hypothesis(id="H1.1", text="test 50%", category="Desirability", quadrant="q1"),
            Hypothesis(id="H1.2", text="test 60%", category="Desirability", quadrant="q1"),
            Hypothesis(id="H1.3", text="test 70%", category="Desirability", quadrant="q1"),
            Hypothesis(id="H2.1", text="test €100", category="Viability", quadrant="q2"),
            Hypothesis(id="H2.2", text="test €200", category="Viability", quadrant="q2"),
            # Missing Feasibility
        ])


def test_hypotheses_all_categories_passes():
    data = Hypotheses(hypotheses=[
        Hypothesis(id="H1.1", text="test 50%", category="Desirability", quadrant="q1"),
        Hypothesis(id="H2.1", text="test €100", category="Viability", quadrant="q2"),
        Hypothesis(id="H3.1", text="test 2 weeks", category="Feasibility", quadrant="q3"),
        Hypothesis(id="H3.2", text="test 95%", category="Feasibility", quadrant="q3"),
        Hypothesis(id="H1.2", text="test 80%", category="Desirability", quadrant="q1"),
    ])
    result = _postprocess_hypotheses(data)
    assert len(result["hypotheses"]) == 5


def _make_what_if_scenario(vector: str, color: str, icon: str, status: str) -> WhatIfScenario:
    return WhatIfScenario(
        id=uuid4(),
        vector=vector,  # type: ignore[arg-type]
        color=color,  # type: ignore[arg-type]
        icon=icon,  # type: ignore[arg-type]
        title="What if title",
        description="description",
        value="value",
        revenue="€1M",
        status=status,  # type: ignore[arg-type]
    )


def test_what_if_order_guaranteed():
    # Input in wrong order: Emotional, Financial, Technical
    data = WhatIf(scenarios=[
        _make_what_if_scenario("Emotional", "slate", "heartHandshake", "draft"),
        _make_what_if_scenario("Financial", "indigo", "coins", "draft"),
        _make_what_if_scenario("Technical", "teal", "cpu", "draft"),
    ])
    result = _postprocess_what_if(data)
    vectors = [s["vector"] for s in result["scenarios"]]
    assert vectors == ["Financial", "Technical", "Emotional"]


def test_what_if_color_icon_deterministic():
    data = WhatIf(scenarios=[
        _make_what_if_scenario("Financial", "slate", "cpu", "draft"),   # wrong color/icon
        _make_what_if_scenario("Technical", "indigo", "heartHandshake", "draft"),
        _make_what_if_scenario("Emotional", "teal", "coins", "draft"),
    ])
    result = _postprocess_what_if(data)
    scenarios = {s["vector"]: s for s in result["scenarios"]}
    assert scenarios["Financial"]["color"] == "indigo"
    assert scenarios["Financial"]["icon"] == "coins"
    assert scenarios["Technical"]["color"] == "teal"
    assert scenarios["Technical"]["icon"] == "cpu"
    assert scenarios["Emotional"]["color"] == "slate"
    assert scenarios["Emotional"]["icon"] == "heartHandshake"


def test_what_if_status_applied_first():
    data = WhatIf(scenarios=[
        _make_what_if_scenario("Financial", "indigo", "coins", "draft"),
        _make_what_if_scenario("Technical", "teal", "cpu", "draft"),
        _make_what_if_scenario("Emotional", "slate", "heartHandshake", "draft"),
    ])
    result = _postprocess_what_if(data)
    statuses = [s["status"] for s in result["scenarios"]]
    assert statuses == ["applied", "draft", "draft"]


# Architecture no longer has bespoke postprocessing — see
# tests/test_architecture_generator.py for its generator-level coverage
# (schema now comes from bizstruct_domain).


def _make_pitch() -> Pitch:
    def inv(t: str) -> InvestorSlide:
        return InvestorSlide(type=t, headline="headline", content="content")  # type: ignore[arg-type]

    def cli(t: str) -> ClientSlide:
        return ClientSlide(type=t, headline="headline", content="content")  # type: ignore[arg-type]

    locale = PitchLocale(
        investor=[inv("ask"), inv("traction"), inv("solution"), inv("problem"), inv("hook")],
        client=[cli("invitation"), cli("social_proof"), cli("transformation"), cli("empathy"), cli("opening")],
    )
    return Pitch(uk=locale, en=locale)


def test_pitch_order_fixed():
    data = _make_pitch()
    result = _postprocess_pitch(data)
    investor_types = [s["type"] for s in result["uk"]["investor"]]
    client_types = [s["type"] for s in result["uk"]["client"]]
    assert investor_types == ["hook", "problem", "solution", "traction", "ask"]
    assert client_types == ["opening", "empathy", "transformation", "social_proof", "invitation"]


# Scenario has no postprocessing of its own anymore — it's sourced from
# bizstruct_domain, which enforces step order/icon pairing itself (see
# bizstruct-domain's test_scenario.py) and no longer carries `highlight`
# (that's presentation logic, moved to the frontend).
