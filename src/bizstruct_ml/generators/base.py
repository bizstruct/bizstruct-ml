from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bizstruct_ml.config import settings
from bizstruct_ml.llm.client import LLMClient, LLMError
from bizstruct_ml.llm.prompts._shared import context_blocks_used
from bizstruct_ml.observability import tracing
from bizstruct_ml.schemas.project import ProjectState
from bizstruct_ml.validation.degenerate_text import DegenerateTextError, validate_block_text
from bizstruct_domain.blocks.canvas import CanvasGenerated
from bizstruct_domain.blocks.what_if import WhatIfGenerated
from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from bizstruct_domain.blocks.scenario import Scenario
from bizstruct_domain.blocks.pitch import Pitch
from bizstruct_domain.blocks.hypotheses import Hypotheses
from bizstruct_domain.blocks.models_options import ModelsOptions

_MONETIZATION_ORDER = ["subscription", "transaction_fee", "retainer_plus_saas"]


def _postprocess_models_options(data: ModelsOptions) -> dict:
    order = {m: i for i, m in enumerate(_MONETIZATION_ORDER)}
    sorted_options = sorted(data.options, key=lambda o: order.get(o.monetization.value, 99))
    result = data.model_copy(
        update={
            "options": [o.model_copy(update={"id": uuid4()}) for o in sorted_options],
            "selected_id": None,
        }
    )
    return result.model_dump(mode="json")


def _postprocess_canvas(data: CanvasGenerated) -> dict:
    dump = data.model_dump(mode="json")
    for section_items in dump.values():
        if isinstance(section_items, list):
            for item in section_items:
                item["id"] = str(uuid4())
                item["is_ai_generated"] = True
    return dump


def _postprocess_what_if(data: WhatIfGenerated) -> dict:
    # Only the id is assigned here (placeholder -> real, same as every
    # other block). Status is NOT touched: WhatIfGenerated's own validator
    # already guarantees every alternative came back status=draft — see
    # bizstruct-domain's what_if module docstring, B1. Deciding which (if
    # any) alternative is applied is a user action on the persisted Canvas/
    # WhatIf, not something generation or postprocessing does.
    fixed = [alt.model_copy(update={"id": uuid4()}) for alt in data.alternatives]
    return WhatIfGenerated(alternatives=fixed).model_dump(mode="json")


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
            retry=retry_if_exception_type((LLMError, ValidationError, DegenerateTextError)),
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

            # Pydantic's own schema (min_length/max_length/enums/cross-field
            # validators) can't catch a syntactically-valid-but-degenerate
            # string — see validation/degenerate_text.py's module docstring.
            # Always recorded to Langfuse (even log-only violations), since
            # otherwise there's no way to measure how often this happens
            # across a real experimental run.
            with tracing.span("validate_text") as vt_span:
                violations = validate_block_text(self.schema, data, project.language or "en")
                vt_span.update(
                    metadata={
                        "violations": [
                            {"field": v.field_path, "kind": v.kind, "detail": v.detail, "retry_worthy": v.retry_worthy}
                            for v in violations
                        ]
                    }
                )
                retry_worthy = [v for v in violations if v.retry_worthy]
                if retry_worthy:
                    raise DegenerateTextError(retry_worthy)

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


class CanvasGenerator(BaseGenerator):
    block = "canvas"
    schema = CanvasGenerated

    def build_prompt(self, project: ProjectState) -> list[dict]:
        from bizstruct_ml.llm.prompts.canvas import build_messages
        return build_messages(project)

    def postprocess(self, data: BaseModel) -> dict:
        return _postprocess_canvas(data)  # type: ignore[arg-type]


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
    schema = WhatIfGenerated

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
