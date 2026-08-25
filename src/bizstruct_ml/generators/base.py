from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bizstruct_ml.config import settings
from bizstruct_ml.llm.client import LLMClient, LLMError
from bizstruct_ml.schemas.project import ProjectState
from bizstruct_ml.schemas.blocks.models_options import ModelsOptions
from bizstruct_ml.schemas.blocks.canvas_data import CanvasData
from bizstruct_ml.schemas.blocks.hypotheses import Hypotheses
from bizstruct_ml.schemas.blocks.what_if import WhatIf, WhatIfScenario
from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_ml.schemas.blocks.pitch import Pitch, INVESTOR_ORDER, CLIENT_ORDER
from bizstruct_ml.schemas.blocks.scenario import Scenario

_VECTOR_COLOR = {"Financial": "indigo", "Technical": "teal", "Emotional": "slate"}
_VECTOR_ICON = {"Financial": "coins", "Technical": "cpu", "Emotional": "heartHandshake"}
_MONETIZATION_ORDER = ["subscription", "transaction_fee", "retainer_plus_saas"]


def _postprocess_models_options(data: ModelsOptions) -> dict:
    order = {m: i for i, m in enumerate(_MONETIZATION_ORDER)}
    sorted_models = sorted(data.models, key=lambda m: order.get(m.monetization, 99))
    result = data.model_copy(
        update={
            "models": [m.model_copy(update={"id": uuid4()}) for m in sorted_models],
            "selected_id": None,
        }
    )
    return result.model_dump(mode="json")


def _postprocess_canvas_data(data: CanvasData) -> dict:
    dump = data.model_dump(mode="json")
    for section_items in dump.values():
        if isinstance(section_items, list):
            for item in section_items:
                item["id"] = str(uuid4())
                item["is_ai_generated"] = True
    return dump


def _postprocess_hypotheses(data: Hypotheses) -> dict:
    categories = {h.category for h in data.hypotheses}
    required = {"Desirability", "Viability", "Feasibility"}
    missing = required - categories
    if missing:
        raise ValidationError.from_exception_data(
            title="Hypotheses",
            input_type="python",
            line_errors=[{
                "type": "value_error",
                "loc": ("hypotheses",),
                "msg": f"Missing hypotheses for categories: {missing}",
                "input": data.hypotheses,
                "ctx": {"error": ValueError(f"Missing categories: {missing}")},
            }],
        )
    return data.model_dump(mode="json")


def _postprocess_what_if(data: WhatIf) -> dict:
    vector_order = ["Financial", "Technical", "Emotional"]
    sorted_scenarios = sorted(
        data.scenarios,
        key=lambda s: vector_order.index(s.vector) if s.vector in vector_order else 99,
    )
    fixed: list[WhatIfScenario] = []
    for i, s in enumerate(sorted_scenarios):
        fixed.append(s.model_copy(update={
            "id": uuid4(),
            "color": _VECTOR_COLOR[s.vector],
            "icon": _VECTOR_ICON[s.vector],
            "status": "applied" if i == 0 else "draft",
        }))
    return WhatIf(scenarios=fixed).model_dump(mode="json")


def _postprocess_pitch(data: Pitch) -> dict:
    dump = data.model_dump(mode="json")
    for locale in dump.values():
        inv = locale["investor"]
        inv.sort(key=lambda s: INVESTOR_ORDER.index(s["type"]) if s["type"] in INVESTOR_ORDER else 99)
        cli = locale["client"]
        cli.sort(key=lambda s: CLIENT_ORDER.index(s["type"]) if s["type"] in CLIENT_ORDER else 99)
    return dump


def _postprocess_scenario(data: Scenario) -> dict:
    ACTION_RESULT = {"scenario.step.action", "scenario.step.result"}
    dump = data.model_dump(mode="json")
    for locale in dump.values():
        for step in locale["timeline"]:
            step["highlight"] = step["label_key"] in ACTION_RESULT
    return dump


class BaseGenerator:
    block: str
    schema: type[BaseModel]
    _llm: LLMClient | None = None

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def build_prompt(self, project: ProjectState) -> list[dict]:
        raise NotImplementedError

    def postprocess(self, data: BaseModel) -> dict:
        return data.model_dump(mode="json")

    async def generate(self, project: ProjectState) -> dict:
        llm = self._get_llm()

        @retry(
            stop=stop_after_attempt(settings.llm_max_retries + 1),
            wait=wait_exponential(min=2, max=8),
            retry=retry_if_exception_type((LLMError, ValidationError)),
            reraise=True,
        )
        async def _run() -> dict:
            messages = self.build_prompt(project)
            result = await llm.generate_structured(messages, self.schema)
            return self.postprocess(result)

        return await _run()


class ModelsOptionsGenerator(BaseGenerator):
    block = "models_options"
    schema = ModelsOptions

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.models_options import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_models_options(data)  # type: ignore[arg-type]


class CanvasDataGenerator(BaseGenerator):
    block = "canvas_data"
    schema = CanvasData

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.canvas_data import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_canvas_data(data)  # type: ignore[arg-type]


class EmpathyMapGenerator(BaseGenerator):
    block = "empathy_map"

    def __init__(self) -> None:
        from bizstruct_ml.schemas.blocks.empathy_map import EmpathyMap
        self.schema = EmpathyMap

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.empathy_map import build_messages
        return build_messages(project)


class HypothesesGenerator(BaseGenerator):
    block = "hypotheses"
    schema = Hypotheses

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.hypotheses import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_hypotheses(data)  # type: ignore[arg-type]


class PitchGenerator(BaseGenerator):
    block = "pitch"
    schema = Pitch

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.pitch import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_pitch(data)  # type: ignore[arg-type]


class ScenarioGenerator(BaseGenerator):
    block = "scenario"
    schema = Scenario

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.scenario import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_scenario(data)  # type: ignore[arg-type]


class WhatIfGenerator(BaseGenerator):
    block = "what_if"
    schema = WhatIf

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.what_if import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_what_if(data)  # type: ignore[arg-type]


class ArchitectureGenerator(BaseGenerator):
    block = "architecture"
    schema = Architecture

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.architecture import build_messages
        return build_messages(project)

    # No postprocessing needed — bizstruct_domain.blocks.architecture.Architecture
    # is a flat model with no derived/status fields to fix up; the default
    # BaseGenerator.postprocess() (a plain model_dump) is sufficient.
