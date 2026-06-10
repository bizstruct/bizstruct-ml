from pydantic import BaseModel, Field


class EmpathyItem(BaseModel):
    id: int
    text: str


class EmpathyLocale(BaseModel):
    says: list[EmpathyItem] = Field(min_length=2, max_length=3)
    thinks: list[EmpathyItem] = Field(min_length=2, max_length=3)
    does: list[EmpathyItem] = Field(min_length=2, max_length=3)
    feels: list[EmpathyItem] = Field(min_length=2, max_length=3)
    pains: list[EmpathyItem] = Field(min_length=2, max_length=3)
    gains: list[EmpathyItem] = Field(min_length=2, max_length=3)


class EmpathyMap(BaseModel):
    uk: EmpathyLocale
    en: EmpathyLocale
