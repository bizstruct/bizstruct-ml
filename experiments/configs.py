"""The systems an experiment can run an idea through. A config starts one project for one idea and returns its id;
the runner then polls it, checks it and measures it the same way for every config.

Adding a config is one class (below) plus one entry in `CONFIGS`."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from experiments.client import Session, create_project
from experiments.ideaset import IdeaInput


@dataclass(frozen=True)
class RunOptions:
    enabled_optional: tuple[str, ...] = ()


class Config(ABC):
    name: str

    def __init__(self, options: RunOptions) -> None:
        self.options = options

    @abstractmethod
    async def start(self, session: Session, idea: IdeaInput) -> str:
        """Start a project for the idea on the system under test and return its project id."""

    async def teardown(self, session: Session, project_id: str) -> None:
        """Called after the run has ended, whatever its outcome (nothing to clean up by default)."""


class PipelineConfig(Config):
    """The slice 1-4 pipeline: be's `POST /api/generation` with autoApprove, so every stage runs without a person."""

    name = "pipeline"

    async def start(self, session: Session, idea: IdeaInput) -> str:
        project = await create_project(
            session, idea=idea.text, language=idea.language, enabled_optional=list(self.options.enabled_optional)
        )
        return project["id"]


CONFIGS: dict[str, type[Config]] = {PipelineConfig.name: PipelineConfig}


def get_config(name: str, options: RunOptions) -> Config:
    if name not in CONFIGS:
        raise KeyError(f"unknown config {name!r}; known: {', '.join(sorted(CONFIGS))}")
    return CONFIGS[name](options)
