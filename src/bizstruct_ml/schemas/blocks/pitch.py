from typing import Literal

from pydantic import BaseModel, Field

InvestorSlideType = Literal["hook", "problem", "solution", "traction", "ask"]
ClientSlideType = Literal["opening", "empathy", "transformation", "social_proof", "invitation"]

INVESTOR_ORDER: list[str] = ["hook", "problem", "solution", "traction", "ask"]
CLIENT_ORDER: list[str] = ["opening", "empathy", "transformation", "social_proof", "invitation"]


class InvestorSlide(BaseModel):
    type: InvestorSlideType
    headline: str = Field(max_length=80)
    content: str


class ClientSlide(BaseModel):
    type: ClientSlideType
    headline: str = Field(max_length=80)
    content: str


class PitchLocale(BaseModel):
    investor: list[InvestorSlide] = Field(min_length=5, max_length=5)
    client: list[ClientSlide] = Field(min_length=5, max_length=5)


class Pitch(BaseModel):
    uk: PitchLocale
    en: PitchLocale
