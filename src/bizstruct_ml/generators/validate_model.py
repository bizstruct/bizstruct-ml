from typing import Any, Literal

from pydantic import BaseModel

from bizstruct_ml.llm.client import LLMClient


class _FieldFeedback(BaseModel):
    field: Literal["title", "audience", "value_proposition", "description"]
    status: Literal["ok", "weak", "invalid"]
    comment: str
    suggestion: str | None = None


class _ValidationResult(BaseModel):
    status: Literal["valid", "needs_revision", "invalid"]
    score: int
    summary: str
    fields: list[_FieldFeedback]


_SYSTEM = """\
You are a senior business strategist and model validator. Evaluate the provided business model concept \
for clarity, specificity, internal consistency, and market viability.

Be constructive: point out concrete weaknesses and suggest specific improvements. \
Do not be overly positive — a score above 80 means genuinely strong work.

Score guidelines:
- 85-100: Exceptionally clear, specific, differentiated
- 70-84: Good with minor gaps
- 50-69: Several issues that need addressing
- Below 50: Fundamental problems"""


async def run_validate_model(payload: dict[str, Any]) -> dict[str, Any]:
    llm = LLMClient()
    try:
        user = (
            f"Validate this business model:\n\n"
            f"Title: {payload.get('title', '')}\n"
            f"Target Audience: {payload.get('audience', '')}\n"
            f"Value Proposition: {payload.get('value_proposition', '')}\n"
            f"Description: {payload.get('description', '')}\n\n"
            f"Return your analysis as structured JSON."
        )
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]
        result = await llm.generate_structured(messages, _ValidationResult)
        assert isinstance(result, _ValidationResult)
        return {
            "model_id": payload.get("model_id"),
            "status": result.status,
            "score": result.score,
            "summary": result.summary,
            "fields": [f.model_dump() for f in result.fields],
        }
    finally:
        await llm.aclose()
