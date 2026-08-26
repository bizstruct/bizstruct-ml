"""Postprocessing invariants — tested without LLM calls."""
import pytest
from uuid import UUID
from pydantic import ValidationError

from bizstruct_ml.generators.base import (
    _postprocess_models_options,
    _postprocess_canvas,
    _postprocess_what_if,
)
from bizstruct_domain.blocks.models_options import ModelsOptions, BusinessModelOption
from bizstruct_domain.blocks.canvas import CanvasGenerated, CanvasCard
from bizstruct_domain.blocks.what_if import ERRCMove, WhatIfAlternative, WhatIfGenerated
from bizstruct_domain.enums import CanvasSection, ERRCAction
from uuid import uuid4


def _make_option(monetization: str, score: int = 80) -> BusinessModelOption:
    return BusinessModelOption(
        id=uuid4(),
        title=f"Model {monetization}",
        audience="mid-market sustainability teams",
        value_proposition="A value proposition long enough to satisfy the domain model's minimum length.",
        description="A description long enough to satisfy the domain model's minimum length.",
        monetization=monetization,  # type: ignore[arg-type]
        key_metric="MRR",
        time_to_value="30 min",
        score=score,
        score_rationale="A rationale long enough to satisfy the domain model's minimum length.",
    )


def test_models_options_order_guaranteed():
    # Input is in wrong order: retainer_plus_saas, subscription, transaction_fee
    data = ModelsOptions(
        options=[
            _make_option("retainer_plus_saas"),
            _make_option("subscription"),
            _make_option("transaction_fee"),
        ],
        selected_id=None,
    )
    result = _postprocess_models_options(data)
    order = [o["monetization"] for o in result["options"]]
    assert order == ["subscription", "transaction_fee", "retainer_plus_saas"]


def test_models_options_selected_id_nulled():
    options = [
        _make_option("subscription"),
        _make_option("transaction_fee"),
        _make_option("retainer_plus_saas"),
    ]
    data = ModelsOptions(options=options, selected_id=options[0].id)
    result = _postprocess_models_options(data)
    assert result["selected_id"] is None


def test_models_options_uuids_regenerated():
    original_ids = [uuid4() for _ in range(3)]
    data = ModelsOptions(
        options=[
            _make_option("subscription"),
            _make_option("transaction_fee"),
            _make_option("retainer_plus_saas"),
        ],
    )
    for o, oid in zip(data.options, original_ids):
        object.__setattr__(o, "id", oid)
    result = _postprocess_models_options(data)
    result_ids = [o["id"] for o in result["options"]]
    assert all(rid not in [str(oid) for oid in original_ids] for rid in result_ids)


def _make_canvas_card(text: str) -> CanvasCard:
    return CanvasCard(id=uuid4(), text=text, is_ai_generated=False)


def test_canvas_uuids_regenerated():
    original_id = uuid4()
    card = CanvasCard(id=original_id, text="A test card", is_ai_generated=False)
    data = CanvasGenerated(
        key_partners=[card, card],
        key_activities=[card, card],
        key_resources=[card, card],
        value_propositions=[card, card],
        customer_relationships=[card, card],
        channels=[card, card],
        customer_segments=[card, card],
        cost_structure=[card, card],
        revenue_streams=[card, card],
    )
    result = _postprocess_canvas(data)
    for items in result.values():
        for it in items:
            assert it["id"] != str(original_id)
            assert it["is_ai_generated"] is True


# Hypotheses has no postprocessing of its own anymore — it's sourced from
# bizstruct_domain, which enforces D/V/F category coverage itself via a
# cross-field validator (see bizstruct-domain's test_hypotheses.py).


def _make_move(action: ERRCAction) -> ERRCMove:
    kwargs = dict(
        action=action,
        target_section=CanvasSection.KEY_PARTNERS,
        target="Third-party logistics partner",
        rationale_uk="Скорочує залежність від зовнішнього партнера.",
        rationale_en="Reduces dependency on an external partner.",
    )
    if action in (ERRCAction.REDUCE, ERRCAction.RAISE_):
        kwargs["new_text"] = "Regional logistics partner, smaller contract"
    return ERRCMove(**kwargs)


def _make_alternative() -> WhatIfAlternative:
    return WhatIfAlternative(
        id=uuid4(),
        title_uk="Пряма доставка",
        title_en="Direct delivery",
        premise_uk="Прибрати посередників у логістиці.",
        premise_en="Remove logistics intermediaries.",
        moves=[
            _make_move(ERRCAction.ELIMINATE),
            _make_move(ERRCAction.REDUCE),
            _make_move(ERRCAction.RAISE_),
        ],
        expected_impact_uk="Нижча собівартість доставки.",
        expected_impact_en="Lower delivery cost.",
    )


def test_what_if_uuids_regenerated():
    original_ids = [uuid4() for _ in range(3)]
    alts = [_make_alternative() for _ in range(3)]
    for alt, oid in zip(alts, original_ids):
        object.__setattr__(alt, "id", oid)
    data = WhatIfGenerated(alternatives=alts)
    result = _postprocess_what_if(data)
    result_ids = [a["id"] for a in result["alternatives"]]
    assert all(rid not in [str(oid) for oid in original_ids] for rid in result_ids)


def test_what_if_status_left_draft():
    """Postprocessing must not assign `applied` — that's a user decision,
    not a generation-time default (bizstruct-domain what_if module
    docstring, B1)."""
    data = WhatIfGenerated(alternatives=[_make_alternative() for _ in range(3)])
    result = _postprocess_what_if(data)
    statuses = [a["status"] for a in result["alternatives"]]
    assert statuses == ["draft", "draft", "draft"]


# Architecture no longer has bespoke postprocessing — see
# tests/test_architecture_generator.py for its generator-level coverage
# (schema now comes from bizstruct_domain).


# Pitch has no postprocessing of its own anymore — it's sourced from
# bizstruct_domain, which enforces slide order itself via a cross-field
# validator (see bizstruct-domain's test_pitch.py), and the audience field
# is `customer` there, not `client`.


# Scenario has no postprocessing of its own anymore — it's sourced from
# bizstruct_domain, which enforces step order/icon pairing itself (see
# bizstruct-domain's test_scenario.py) and no longer carries `highlight`
# (that's presentation logic, moved to the frontend).
