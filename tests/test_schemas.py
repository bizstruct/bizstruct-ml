"""Validate example JSON from ML Generation Specification against Pydantic schemas."""
import pytest
from bizstruct_ml.schemas.blocks import (
    ModelsOptions,
    CanvasGenerated,
    EmpathyMap,
    Hypotheses,
    Pitch,
    Scenario,
    WhatIf,
    Architecture,
)


MODELS_OPTIONS_EXAMPLE = {
    "options": [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "title": "B2B SaaS · EcoSync",
            "audience": "mid-market",
            "value_proposition": "Automate ESG reporting in minutes",
            "description": "Monthly subscription giving mid-market companies automated ESG reporting. Reduces compliance costs by 80%.",
            "monetization": "subscription",
            "key_metric": "MRR / NRR",
            "time_to_value": "30 minutes to first report",
            "score": 91,
            "score_rationale": "High: directly automates the Empathy Map's top pain (manual reporting) with a proven SaaS pricing model.",
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "title": "Marketplace · EcoSync",
            "audience": "SMB",
            "value_proposition": "Pay per report generated",
            "description": "Transaction fee per ESG report submitted. Scales with customer usage.",
            "monetization": "transaction_fee",
            "key_metric": "GMV / take rate",
            "time_to_value": "15 minutes to first report",
            "score": 72,
            "score_rationale": "Moderate: lowers the entry barrier for SMBs but revenue is less predictable than subscription.",
        },
        {
            "id": "00000000-0000-0000-0000-000000000003",
            "title": "Advisory · EcoSync",
            "audience": "enterprise",
            "value_proposition": "Expert advisory plus platform access",
            "description": "Retainer for ESG strategy consulting combined with SaaS access.",
            "monetization": "retainer_plus_saas",
            "key_metric": "ACV",
            "time_to_value": "2 weeks onboarding",
            "score": 65,
            "score_rationale": "Lower: higher-touch sales cycle and smaller addressable market than the other two options.",
        },
    ],
    "selected_id": None,
}

CANVAS_EXAMPLE = {
    "key_partners": [
        {"id": "00000000-0000-0000-0000-000000000010", "text": "ESG data providers", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000011", "text": "Regulatory bodies", "is_ai_generated": True},
    ],
    "key_activities": [
        {"id": "00000000-0000-0000-0000-000000000020", "text": "AI model training", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000021", "text": "Data integration", "is_ai_generated": True},
    ],
    "key_resources": [
        {"id": "00000000-0000-0000-0000-000000000030", "text": "AI/ML infrastructure", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000031", "text": "ESG expertise team", "is_ai_generated": True},
    ],
    "value_propositions": [
        {"id": "00000000-0000-0000-0000-000000000040", "text": "80% reduction in reporting time", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000041", "text": "Regulatory compliance guaranteed", "is_ai_generated": True},
    ],
    "customer_relationships": [
        {"id": "00000000-0000-0000-0000-000000000050", "text": "Dedicated success manager", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000051", "text": "Self-serve onboarding", "is_ai_generated": True},
    ],
    "channels": [
        {"id": "00000000-0000-0000-0000-000000000060", "text": "Direct sales", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000061", "text": "ESG consultant partnerships", "is_ai_generated": True},
    ],
    "customer_segments": [
        {"id": "00000000-0000-0000-0000-000000000070", "text": "Mid-market manufacturing firms", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000071", "text": "Financial institutions", "is_ai_generated": True},
    ],
    "cost_structure": [
        {"id": "00000000-0000-0000-0000-000000000080", "text": "Cloud infrastructure ~€120k/year", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000081", "text": "R&D team salaries", "is_ai_generated": True},
    ],
    "revenue_streams": [
        {"id": "00000000-0000-0000-0000-000000000090", "text": "Monthly SaaS subscription €500-€5000", "is_ai_generated": True},
        {"id": "00000000-0000-0000-0000-000000000091", "text": "Premium support tier", "is_ai_generated": True},
    ],
}

def _empathy_item(i: int, text: str) -> dict:
    return {"id": i, "text": text}


EMPATHY_MAP_EXAMPLE = {
    "says": [
        _empathy_item(1, "Reporting takes 3 weeks"),
        _empathy_item(2, "Need an automated process"),
        _empathy_item(3, "We're falling behind competitors"),
    ],
    "thinks": [
        _empathy_item(1, "Fine for non-compliance"),
        _empathy_item(2, "Competitors already automated"),
        _empathy_item(3, "This should be simpler"),
    ],
    "does": [
        _empathy_item(1, "Collects data manually in Excel"),
        _empathy_item(2, "Hires external consultants"),
        _empathy_item(3, "Double-checks the report repeatedly"),
    ],
    "feels": [
        _empathy_item(1, "Stressed before deadlines"),
        _empathy_item(2, "Uncertain about data accuracy"),
        _empathy_item(3, "Fatigued by repetitive work"),
    ],
    "pains": [
        _empathy_item(1, "80 hours/quarter on data collection"),
        _empathy_item(2, "Errors in reports = fine risk"),
        _empathy_item(3, "Data scattered across systems"),
    ],
    "gains": [
        _empathy_item(1, "Automated data collection"),
        _empathy_item(2, "Compliance with GRI/TCFD standards"),
        _empathy_item(3, "More time for analysis, not collection"),
    ],
}

HYPOTHESES_EXAMPLE = {
    "hypotheses": [
        {"id": "H1.1", "text": "60% of CFOs spend >40h/quarter on ESG reporting", "category": "desirability", "quadrant": "q1"},
        {"id": "H1.2", "text": "80% would switch to an automated solution", "category": "desirability", "quadrant": "q1"},
        {"id": "H2.1", "text": "Mid-market firms pay €2000/month for ESG tools", "category": "viability", "quadrant": "q2"},
        {"id": "H3.1", "text": "AI can achieve 95% accuracy on standard ESG frameworks", "category": "feasibility", "quadrant": "q3"},
        {"id": "H3.2", "text": "Integration with ERP systems takes <2 weeks", "category": "feasibility", "quadrant": "q3"},
    ]
}

def _pitch_slide(slide_type: str, headline: str, content: str) -> dict:
    return {"type": slide_type, "headline": headline, "content": content}


PITCH_EXAMPLE = {
    "investor": [
        _pitch_slide("hook", "ESG reporting costs €240k/year and 3 weeks",
                     "Every public company must report. None want to waste time on it."),
        _pitch_slide("problem", "Companies drown in Excel and consultants",
                     "80 hours per quarter, 15% error rate, €50k+ on external consultants."),
        _pitch_slide("solution", "EcoSync: ESG automation in 30 minutes",
                     "AI collects, analyzes, and generates reports automatically. Supports GRI, TCFD, CSRD."),
        _pitch_slide("traction", "Potentially 500+ companies in pipeline",
                     "Example: first 10 clients could save €1.2M collectively."),
        _pitch_slide("ask", "Raising €2M seed round",
                     "For product development and acquiring first 50 enterprise clients."),
    ],
    "customer": [
        _pitch_slide("opening", "Your ESG report is ready. In 30 minutes.",
                     "Not 3 weeks, not €50k. In 30 minutes."),
        _pitch_slide("empathy", "We know: data collection is hell",
                     "80 hours per quarter, cross-department misalignment, fear of errors."),
        _pitch_slide("transformation", "With EcoSync reporting becomes routine, not crisis",
                     "Automatic collection, validation, report generation in one click."),
        _pitch_slide("social_proof", "Example: CFO saved 70 hours per quarter",
                     "Potential savings of €40k/year for companies with 500+ employees."),
        _pitch_slide("invitation", "Try free for 30 days",
                     "Connect your data — first report ready today."),
    ],
}

SCENARIO_EXAMPLE = {
    "persona": {
        "name": "Elena Koval",
        "role": "CFO, manufacturing company",
        "pain_point": "Quarterly ESG report preparation takes 3 weeks and disrupts all plans",
    },
    "timeline": [
        {"step_type": "context", "text": "End of quarter — ESG report deadline in 3 weeks"},
        {"step_type": "goal", "text": "Collect data from 12 departments and prepare the report"},
        {"step_type": "action", "text": "Elena connects EcoSync to ERP and Excel files"},
        {"step_type": "result", "text": "In 45 minutes system collected and validated all data"},
        {"step_type": "impact", "text": "Report ready 2 weeks early, team saved 70 hours"},
    ],
    "metrics": {
        "before": {"value": "3 weeks", "label": "Time to prepare ESG report"},
        "after": {"value": "45 minutes", "label": "Time with EcoSync"},
    },
}

def _errc_move(action: str, section: str, target: str, new_text: str | None = None) -> dict:
    move = {
        "action": action,
        "target_section": section,
        "target": target,
        "rationale": "Rationale for this move, long enough to pass validation.",
    }
    if action in ("reduce", "raise"):
        move["new_text"] = new_text or "Replacement text for the existing card, long enough to pass validation"
    return move


WHAT_IF_EXAMPLE = {
    "alternatives": [
        {
            "id": "00000000-0000-0000-0000-000000000100",
            "title": "Outcome-based pricing",
            "premise": "Charge only when the ESG report passes regulatory review.",
            "moves": [
                _errc_move("eliminate", "revenue_streams", "Fixed monthly subscription fee"),
                _errc_move("reduce", "cost_structure", "Upfront onboarding cost"),
                _errc_move("raise", "value_propositions", "Regulatory-review guarantee"),
            ],
            "expected_impact": "Potential 2x revenue per client.",
            "status": "draft",
        },
        {
            "id": "00000000-0000-0000-0000-000000000101",
            "title": "Real-time ESG monitoring",
            "premise": "Continuous data collection instead of quarterly batch processing.",
            "moves": [
                _errc_move("eliminate", "key_activities", "Quarterly manual data review"),
                _errc_move("raise", "key_resources", "Real-time data pipeline"),
                _errc_move("create", "revenue_streams", "Premium real-time monitoring tier"),
            ],
            "expected_impact": "Premium tier with higher retention.",
            "status": "draft",
        },
        {
            "id": "00000000-0000-0000-0000-000000000102",
            "title": "Sustainability leadership brand",
            "premise": "Reframe ESG from compliance burden to brand differentiator.",
            "moves": [
                _errc_move("reduce", "customer_relationships", "Purely transactional support"),
                _errc_move("raise", "channels", "Public sustainability showcase"),
                _errc_move("create", "revenue_streams", "Brand partnership revenue stream"),
            ],
            "expected_impact": "New brand partnership revenue stream.",
            "status": "draft",
        },
    ]
}

ARCHITECTURE_EXAMPLE = {
    "epicenter": "customer_driven",
    "epicenter_rationale": "The model is built around the customer's pain — time spent on ESG reporting. Every feature solves a specific CFO problem.",
    "pattern": "free",
    "pattern_subtype": "freemium",
    "pattern_rationale": "Free plan for product discovery, paid plan for full automated reporting without limits.",
}


def test_models_options_schema():
    result = ModelsOptions.model_validate(MODELS_OPTIONS_EXAMPLE)
    assert len(result.options) == 3
    assert result.selected_id is None


def test_canvas_schema():
    result = CanvasGenerated.model_validate(CANVAS_EXAMPLE)
    assert len(result.key_partners) == 2
    assert result.key_partners[0].is_ai_generated is True


def test_empathy_map_schema():
    result = EmpathyMap.model_validate(EMPATHY_MAP_EXAMPLE)
    assert len(result.says) == 3
    assert len(result.pains) == 3
    assert result.pains[0].text == "80 hours/quarter on data collection"


def test_hypotheses_schema():
    result = Hypotheses.model_validate(HYPOTHESES_EXAMPLE)
    assert len(result.hypotheses) == 5
    categories = {h.category for h in result.hypotheses}
    assert categories == {"desirability", "viability", "feasibility"}


def test_pitch_schema():
    result = Pitch.model_validate(PITCH_EXAMPLE)
    assert len(result.investor) == 5
    assert len(result.customer) == 5
    assert result.investor[0].type == "hook"
    assert result.customer[0].type == "opening"


def test_scenario_schema():
    result = Scenario.model_validate(SCENARIO_EXAMPLE)
    assert result.persona.name == "Elena Koval"
    assert len(result.timeline) == 5
    assert result.timeline[0].step_type == "context"


def test_what_if_schema():
    result = WhatIf.model_validate(WHAT_IF_EXAMPLE)
    assert len(result.alternatives) == 3
    assert result.alternatives[0].title == "Outcome-based pricing"
    assert result.alternatives[0].status == "draft"


def test_architecture_schema():
    result = Architecture.model_validate(ARCHITECTURE_EXAMPLE)
    assert result.epicenter.value == "customer_driven"
    assert result.pattern.value == "free"
    assert result.pattern_subtype.value == "freemium"
