from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bizstruct_ml.config import settings
from bizstruct_ml.llm.client import LLMClient, LLMError
from bizstruct_ml.llm.prompts._shared import context_blocks_used
from bizstruct_ml.observability import tracing
from bizstruct_ml.schemas.project import ProjectState
from bizstruct_ml.schemas.blocks.models_options import ModelsOptions
from bizstruct_ml.schemas.blocks.canvas_data import CanvasData
from bizstruct_ml.schemas.blocks.what_if import WhatIf, WhatIfScenario
from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from bizstruct_domain.blocks.scenario import Scenario
from bizstruct_domain.blocks.pitch import Pitch
from bizstruct_domain.blocks.hypotheses import Hypotheses

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

        with tracing.span("build_prompt") as bp_span:
            messages = self.build_prompt(project)
            bp_span.update(output={"context_blocks": context_blocks_used(project)})

        attempts = {"n": 0}

        @retry(
            stop=stop_after_attempt(settings.llm_max_retries + 1),
            wait=wait_exponential(min=2, max=8),
            retry=retry_if_exception_type((LLMError, ValidationError)),
            reraise=True,
        )
        async def _run() -> dict:
            attempts["n"] += 1
            with tracing.generation_span(
                "llm_call",
                model=llm.model_name,
                input=messages,
                metadata={"attempt": attempts["n"]},
            ) as gen_span:
                result = await llm.generate_structured(messages, self.schema)
                gen_span.update(
                    output=result.model_dump(mode="json"),
                    usage_details=llm.last_usage,
                )
            with tracing.span("postprocess") as pp_span:
                data = self.postprocess(result)
                pp_span.update(output=data)
            return data

        try:
            result_data = await _run()
        finally:
            # Retries here mean tenacity caught a ValidationError (bad
            # schema from the LLM) or LLMError and re-ran the whole
            # build->call->postprocess step. attempts["n"] - 1 is the retry
            # count; a direct trace attribute, since it's a straight
            # indicator of prompt quality for this block.
            tracing.update_current_span(metadata={"llm_retry_count": attempts["n"] - 1})

        return result_data


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
    schema = EmpathyMap

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.empathy_map import build_messages
        return build_messages(project)

    # No postprocessing needed — bizstruct_domain.blocks.empathy_map.EmpathyMap
    # has no derived/status fields to fix up.


class HypothesesGenerator(BaseGenerator):
    block = "hypotheses"
    schema = Hypotheses

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.hypotheses import build_messages
        return build_messages(project)

    # No postprocessing needed — bizstruct_domain.blocks.hypotheses.Hypotheses
    # enforces D/V/F category coverage itself via a cross-field validator.


class PitchGenerator(BaseGenerator):
    block = "pitch"
    schema = Pitch

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.pitch import build_messages
        return build_messages(project)

    # No postprocessing needed — bizstruct_domain.blocks.pitch.Pitch enforces
    # slide order itself via a cross-field validator.


class ScenarioGenerator(BaseGenerator):
    block = "scenario"
    schema = Scenario

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.scenario import build_messages
        return build_messages(project)

    # No postprocessing needed — bizstruct_domain.blocks.scenario.Scenario
    # has no derived/status fields to fix up. In particular, step highlighting
    # is no longer computed here: it's presentation logic, moved to the
    # frontend (derived from step_type).


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
