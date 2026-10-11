"""The ideas an experiment runs. `expected_shape` and `tags` are the maintainer's hypotheses and labels for the
analysis; they never leave this module: a config only ever sees an `IdeaInput`."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class IdeaInput(BaseModel):
    """Everything about an idea that is sent to the system under test."""

    model_config = ConfigDict(frozen=True)

    id: str
    language: Literal["en", "uk"]
    text: str


class Idea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The id names files (projects/<id>-<repeat>.json), so it is restricted to a safe alphabet.
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    language: Literal["en", "uk"]
    text: str = Field(min_length=50, max_length=2000)
    # "one_segment" | "multi_sided" | "split" | "ambiguous" | free text: a hypothesis, compared to the outcome in the analysis.
    expected_shape: str = ""
    tags: list[str] = Field(default_factory=list)

    def for_system(self) -> IdeaInput:
        return IdeaInput(id=self.id, language=self.language, text=self.text)


class IdeasFileError(ValueError):
    """The ideas file is not usable; the message names the line."""


def load_ideas(path: Path) -> list[Idea]:
    ideas: list[Idea] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            idea = Idea.model_validate(json.loads(line))
        except json.JSONDecodeError as error:
            raise IdeasFileError(f"{path}:{number}: not JSON ({error.msg})") from error
        except ValidationError as error:
            first = error.errors()[0]
            raise IdeasFileError(f"{path}:{number}: {'.'.join(str(p) for p in first['loc'])}: {first['msg']}") from error
        if idea.id in seen:
            raise IdeasFileError(f"{path}:{number}: duplicate idea id {idea.id!r}")
        seen.add(idea.id)
        ideas.append(idea)
    if not ideas:
        raise IdeasFileError(f"{path}: no ideas")
    return ideas
