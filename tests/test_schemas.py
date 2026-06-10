"""Validate example JSON from ML Generation Specification against Pydantic schemas."""
import pytest
from bizstruct_ml.schemas.blocks import (
    ModelsOptions,
    CanvasData,
    EmpathyMap,
    Hypotheses,
    Pitch,
    Scenario,
    WhatIf,
    Architecture,
)


MODELS_OPTIONS_EXAMPLE = {
    "models": [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "B2B SaaS · EcoSync",
            "tagline": "Automate ESG reporting in minutes",
            "description": "Monthly subscription giving mid-market companies automated ESG reporting. Reduces compliance costs by 80%.",
            "monetization": "subscription",
            "target_segment": "mid-market",
            "key_metric": "MRR / NRR",
            "time_to_value": "30 minutes to first report",
            "score": 91,
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "name": "Marketplace · EcoSync",
            "tagline": "Pay per report generated",
            "description": "Transaction fee per ESG report submitted. Scales with customer usage.",
            "monetization": "transaction_fee",
            "target_segment": "SMB",
            "key_metric": "GMV / take rate",
            "time_to_value": "15 minutes to first report",
            "score": 72,
        },
        {
            "id": "00000000-0000-0000-0000-000000000003",
            "name": "Advisory · EcoSync",
            "tagline": "Expert advisory plus platform access",
            "description": "Retainer for ESG strategy consulting combined with SaaS access.",
            "monetization": "retainer_plus_saas",
            "target_segment": "enterprise",
            "key_metric": "ACV",
            "time_to_value": "2 weeks onboarding",
            "score": 65,
        },
    ],
    "selected_id": None,
}

CANVAS_DATA_EXAMPLE = {
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

EMPATHY_MAP_EXAMPLE = {
    "uk": {
        "says": [{"id": 1, "text": "Звітність займає 3 тижні"}, {"id": 2, "text": "Потрібен автоматизований процес"}],
        "thinks": [{"id": 1, "text": "Штраф за порушення вимог"}, {"id": 2, "text": "Конкуренти вже автоматизували"}],
        "does": [{"id": 1, "text": "Збирає дані вручну в Excel"}, {"id": 2, "text": "Наймає зовнішніх консультантів"}],
        "feels": [{"id": 1, "text": "Стрес перед дедлайнами"}, {"id": 2, "text": "Невпевненість у правильності даних"}],
        "pains": [{"id": 1, "text": "80 годин/квартал на збір даних"}, {"id": 2, "text": "Помилки у звітах = ризик штрафів"}],
        "gains": [{"id": 1, "text": "Автоматичний збір даних"}, {"id": 2, "text": "Відповідність всім стандартам GRI/TCFD"}],
    },
    "en": {
        "says": [{"id": 1, "text": "Reporting takes 3 weeks"}, {"id": 2, "text": "Need an automated process"}],
        "thinks": [{"id": 1, "text": "Fine for non-compliance"}, {"id": 2, "text": "Competitors already automated"}],
        "does": [{"id": 1, "text": "Collects data manually in Excel"}, {"id": 2, "text": "Hires external consultants"}],
        "feels": [{"id": 1, "text": "Stressed before deadlines"}, {"id": 2, "text": "Uncertain about data accuracy"}],
        "pains": [{"id": 1, "text": "80 hours/quarter on data collection"}, {"id": 2, "text": "Errors in reports = fine risk"}],
        "gains": [{"id": 1, "text": "Automated data collection"}, {"id": 2, "text": "Compliance with GRI/TCFD standards"}],
    },
}

HYPOTHESES_EXAMPLE = {
    "hypotheses": [
        {"id": "H1.1", "text": "60% of CFOs spend >40h/quarter on ESG reporting", "category": "Desirability", "quadrant": "q1"},
        {"id": "H1.2", "text": "80% would switch to automated solution", "category": "Desirability", "quadrant": "q1"},
        {"id": "H2.1", "text": "Mid-market firms pay €2000/month for ESG tools", "category": "Viability", "quadrant": "q2"},
        {"id": "H3.1", "text": "AI can achieve 95% accuracy on standard ESG frameworks", "category": "Feasibility", "quadrant": "q3"},
        {"id": "H3.2", "text": "Integration with ERP systems takes <2 weeks", "category": "Feasibility", "quadrant": "q3"},
    ]
}

PITCH_EXAMPLE = {
    "uk": {
        "investor": [
            {"type": "hook", "headline": "ESG-звітність коштує €240k/рік та 3 тижні часу", "content": "Кожна публічна компанія зобов'язана звітувати. Жодна не хоче витрачати на це час."},
            {"type": "problem", "headline": "Компанії тонуть у Excel і консультантах", "content": "80 годин на квартал, 15% помилок у звітах, €50k+ на зовнішніх консультантів."},
            {"type": "solution", "headline": "EcoSync: автоматизація ESG за 30 хвилин", "content": "AI збирає, аналізує і генерує звіти автоматично. Підтримка GRI, TCFD, CSRD."},
            {"type": "traction", "headline": "Потенційно 500+ компаній у pipeline", "content": "Приклад: перші 10 клієнтів можуть заощадити €1.2M сукупно."},
            {"type": "ask", "headline": "Залучаємо €2M seed раунд", "content": "На розвиток продукту та залучення перших 50 enterprise клієнтів."},
        ],
        "client": [
            {"type": "opening", "headline": "Ваш ESG-звіт готовий. За 30 хвилин.", "content": "Не за 3 тижні, не за €50k. За 30 хвилин."},
            {"type": "empathy", "headline": "Ми знаємо: збір даних — це пекло", "content": "80 годин на квартал, неузгодженість між відділами, страх помилок."},
            {"type": "transformation", "headline": "З EcoSync звітність стає рутиною, не кризою", "content": "Автоматичний збір, валідація, генерація звіту в один клік."},
            {"type": "social_proof", "headline": "Приклад: CFO заощадив 70 годин за квартал", "content": "Потенційна економія €40k/рік для компаній розміром 500+ людей."},
            {"type": "invitation", "headline": "Спробуйте безкоштовно 30 днів", "content": "Підключіть ваші дані — перший звіт готовий сьогодні."},
        ],
    },
    "en": {
        "investor": [
            {"type": "hook", "headline": "ESG reporting costs €240k/year and 3 weeks", "content": "Every public company must report. None want to waste time on it."},
            {"type": "problem", "headline": "Companies drown in Excel and consultants", "content": "80 hours per quarter, 15% error rate, €50k+ on external consultants."},
            {"type": "solution", "headline": "EcoSync: ESG automation in 30 minutes", "content": "AI collects, analyzes, and generates reports automatically. Supports GRI, TCFD, CSRD."},
            {"type": "traction", "headline": "Potentially 500+ companies in pipeline", "content": "Example: first 10 clients could save €1.2M collectively."},
            {"type": "ask", "headline": "Raising €2M seed round", "content": "For product development and acquiring first 50 enterprise clients."},
        ],
        "client": [
            {"type": "opening", "headline": "Your ESG report is ready. In 30 minutes.", "content": "Not 3 weeks, not €50k. In 30 minutes."},
            {"type": "empathy", "headline": "We know: data collection is hell", "content": "80 hours per quarter, cross-department misalignment, fear of errors."},
            {"type": "transformation", "headline": "With EcoSync reporting becomes routine, not crisis", "content": "Automatic collection, validation, report generation in one click."},
            {"type": "social_proof", "headline": "Example: CFO saved 70 hours per quarter", "content": "Potential savings of €40k/year for companies with 500+ employees."},
            {"type": "invitation", "headline": "Try free for 30 days", "content": "Connect your data — first report ready today."},
        ],
    },
}

SCENARIO_EXAMPLE = {
    "uk": {
        "persona": {
            "name": "Олена Коваль",
            "initials": "ОК",
            "role": "CFO, виробнича компанія",
            "pain_point": "Щоквартальна підготовка ESG-звіту займає 3 тижні і ламає всі плани",
        },
        "timeline": [
            {"icon_key": "calendar", "label_key": "scenario.step.context", "text": "Кінець кварталу — дедлайн ESG звіту через 3 тижні", "highlight": False},
            {"icon_key": "target", "label_key": "scenario.step.goal", "text": "Зібрати дані від 12 відділів та підготувати звіт", "highlight": False},
            {"icon_key": "zap", "label_key": "scenario.step.action", "text": "Олена підключає EcoSync до ERP та Excel-файлів", "highlight": True},
            {"icon_key": "check-circle", "label_key": "scenario.step.result", "text": "За 45 хвилин система зібрала та валідувала всі дані", "highlight": True},
            {"icon_key": "trending-up", "label_key": "scenario.step.impact", "text": "Звіт готовий на 2 тижні раніше, команда зберегла 70 годин", "highlight": False},
        ],
        "metrics": {
            "before": {"value": "3 тижні", "label": "Час на підготовку ESG звіту"},
            "after": {"value": "45 хвилин", "label": "Час з EcoSync"},
        },
    },
    "en": {
        "persona": {
            "name": "Elena Koval",
            "initials": "EK",
            "role": "CFO, manufacturing company",
            "pain_point": "Quarterly ESG report preparation takes 3 weeks and disrupts all plans",
        },
        "timeline": [
            {"icon_key": "calendar", "label_key": "scenario.step.context", "text": "End of quarter — ESG report deadline in 3 weeks", "highlight": False},
            {"icon_key": "target", "label_key": "scenario.step.goal", "text": "Collect data from 12 departments and prepare the report", "highlight": False},
            {"icon_key": "zap", "label_key": "scenario.step.action", "text": "Elena connects EcoSync to ERP and Excel files", "highlight": True},
            {"icon_key": "check-circle", "label_key": "scenario.step.result", "text": "In 45 minutes system collected and validated all data", "highlight": True},
            {"icon_key": "trending-up", "label_key": "scenario.step.impact", "text": "Report ready 2 weeks early, team saved 70 hours", "highlight": False},
        ],
        "metrics": {
            "before": {"value": "3 weeks", "label": "Time to prepare ESG report"},
            "after": {"value": "45 minutes", "label": "Time with EcoSync"},
        },
    },
}

WHAT_IF_EXAMPLE = {
    "scenarios": [
        {
            "id": "00000000-0000-0000-0000-000000000100",
            "vector": "Financial",
            "color": "indigo",
            "icon": "coins",
            "title": "What if we offered outcome-based pricing?",
            "description": "Charge only when the ESG report passes regulatory review. Aligns incentives with customer success.",
            "value": "Zero risk for the customer — pay only for results",
            "revenue": "Potential 2x revenue per client at €4000/report",
            "status": "applied",
        },
        {
            "id": "00000000-0000-0000-0000-000000000101",
            "vector": "Technical",
            "color": "teal",
            "icon": "cpu",
            "title": "What if we built real-time ESG monitoring?",
            "description": "Continuous data collection instead of quarterly batch processing. Enables proactive compliance.",
            "value": "Always-current ESG score, instant alerts on deviations",
            "revenue": "Premium tier at €8000/month, 30% higher retention",
            "status": "draft",
        },
        {
            "id": "00000000-0000-0000-0000-000000000102",
            "vector": "Emotional",
            "color": "slate",
            "icon": "heartHandshake",
            "title": "What if we made ESG a competitive advantage story?",
            "description": "Reframe ESG from compliance burden to brand differentiator. Help customers market their scores.",
            "value": "Pride in sustainability leadership, not just compliance",
            "revenue": "Brand partnership revenue stream, €500k/year potential",
            "status": "draft",
        },
    ]
}

ARCHITECTURE_EXAMPLE = {
    "uk": {
        "epicenter": {
            "value": "Customer-driven",
            "description": "Модель будується навколо болю клієнта — витрат часу на ESG звітність. Кожна функція вирішує конкретну проблему CFO.",
            "status": "determined",
        },
        "pattern": {
            "value": "FREE",
            "subtype": "Freemium",
            "description": "Безкоштовний план для знайомства з продуктом, платний — для повного автоматизованого звітування.",
            "status": "system_selection",
        },
    },
    "en": {
        "epicenter": {
            "value": "Customer-driven",
            "description": "The model is built around the customer's pain — time spent on ESG reporting. Every feature solves a specific CFO problem.",
            "status": "determined",
        },
        "pattern": {
            "value": "FREE",
            "subtype": "Freemium",
            "description": "Free plan for product discovery, paid plan for full automated reporting.",
            "status": "system_selection",
        },
    },
}


def test_models_options_schema():
    result = ModelsOptions.model_validate(MODELS_OPTIONS_EXAMPLE)
    assert len(result.models) == 3
    assert result.selected_id is None


def test_canvas_data_schema():
    result = CanvasData.model_validate(CANVAS_DATA_EXAMPLE)
    assert len(result.key_partners) == 2
    assert result.key_partners[0].is_ai_generated is True


def test_empathy_map_schema():
    result = EmpathyMap.model_validate(EMPATHY_MAP_EXAMPLE)
    assert len(result.uk.says) == 2
    assert len(result.en.pains) == 2


def test_hypotheses_schema():
    result = Hypotheses.model_validate(HYPOTHESES_EXAMPLE)
    assert len(result.hypotheses) == 5
    categories = {h.category for h in result.hypotheses}
    assert categories == {"Desirability", "Viability", "Feasibility"}


def test_pitch_schema():
    result = Pitch.model_validate(PITCH_EXAMPLE)
    assert len(result.uk.investor) == 5
    assert len(result.en.client) == 5
    assert result.uk.investor[0].type == "hook"


def test_scenario_schema():
    result = Scenario.model_validate(SCENARIO_EXAMPLE)
    assert result.uk.persona.name == "Олена Коваль"
    assert len(result.uk.timeline) == 5


def test_what_if_schema():
    result = WhatIf.model_validate(WHAT_IF_EXAMPLE)
    assert len(result.scenarios) == 3
    assert result.scenarios[0].vector == "Financial"
    assert result.scenarios[0].status == "applied"


def test_architecture_schema():
    result = Architecture.model_validate(ARCHITECTURE_EXAMPLE)
    assert result.uk.epicenter.status == "determined"
    assert result.en.pattern.status == "system_selection"
