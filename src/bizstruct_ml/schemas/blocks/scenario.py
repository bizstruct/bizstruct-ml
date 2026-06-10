from typing import Literal

from pydantic import BaseModel, Field

IconKey = Literal["calendar", "target", "zap", "check-circle", "trending-up"]
LabelKey = Literal[
    "scenario.step.context",
    "scenario.step.goal",
    "scenario.step.action",
    "scenario.step.result",
    "scenario.step.impact",
]


class Persona(BaseModel):
    name: str
    initials: str
    role: str
    pain_point: str


class TimelineStep(BaseModel):
    icon_key: IconKey
    label_key: LabelKey
    text: str
    highlight: bool


class MetricValue(BaseModel):
    value: str
    label: str


class ScenarioMetrics(BaseModel):
    before: MetricValue
    after: MetricValue


class ScenarioLocale(BaseModel):
    persona: Persona
    timeline: list[TimelineStep] = Field(min_length=5, max_length=5)
    metrics: ScenarioMetrics


class Scenario(BaseModel):
    uk: ScenarioLocale
    en: ScenarioLocale
