"""Scripted judge model for tests: no network, replies are queued up front."""

from collections.abc import Callable, Iterable
from typing import ClassVar

from bizstruct_ml.judge.base import JudgeModel, JudgeModelError


class FakeJudgeModel(JudgeModel):
    """Replies with the scripted items in order; the last one repeats.

    An item is a raw reply string, an exception instance to raise, or a
    callable `(system, user) -> str`. Every call is recorded in `calls`.
    """

    family: ClassVar[str] = "fake"

    def __init__(self, replies: Iterable[str | Exception | Callable[[str, str], str]] = ()) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, object]] = []

    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        if not self._replies:
            raise JudgeModelError("FakeJudgeModel has no scripted reply")
        item = self._replies[min(len(self.calls), len(self._replies)) - 1]
        if isinstance(item, Exception):
            raise item
        return item(system, user) if callable(item) else item
