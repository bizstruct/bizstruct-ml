"""Consumer: message settling and the lock-renewal duration from LOCK_RENEWAL_SECONDS."""
import asyncio
import json

import pytest
from bizstruct_domain.schemas import QueueMessage, RowTarget, Stage

from bizstruct_ml.adapters import consumer
from bizstruct_ml.config import Settings
from bizstruct_ml.strategies.pipeline import Action, Disposition


class FakeMessage:
    def __init__(self, body: str, delivery_count: int = 1) -> None:
        self.body = body
        self.delivery_count = delivery_count

    def __str__(self) -> str:
        return self.body


class FakeReceiver:
    def __init__(self, batches: list[list[FakeMessage]]) -> None:
        self._batches = batches
        self.settled: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def receive_messages(self, **kwargs):
        if self._batches:
            return self._batches.pop(0)
        consumer._shutdown.set()
        return []

    async def complete_message(self, msg):
        self.settled.append(("complete", {}))

    async def abandon_message(self, msg):
        self.settled.append(("abandon", {}))

    async def dead_letter_message(self, msg, reason="", error_description=""):
        self.settled.append(("dead_letter", {"reason": reason, "description": error_description}))


def body(project_id: str = "p1") -> str:
    target = RowTarget(stage_row_id="r1", stage=Stage.BRIEF, attempt_id="a1")
    return QueueMessage(project_id=project_id, language="en", targets=[target]).model_dump_json()


@pytest.fixture(autouse=True)
def _reset_shutdown():
    consumer._shutdown.clear()
    yield
    consumer._shutdown.clear()


@pytest.mark.parametrize(
    ("action", "settled"),
    [(Action.COMPLETE, "complete"), (Action.ABANDON, "abandon"), (Action.DEAD_LETTER, "dead_letter")],
)
async def test_the_disposition_decides_how_the_message_is_settled(monkeypatch, action, settled):
    async def fake_handle(message, backend, runner, *, delivery_count=1):
        return Disposition(action=action, reason="Why", description="Because")

    monkeypatch.setattr(consumer, "handle_message", fake_handle)
    receiver = FakeReceiver([])
    await consumer.process_message(receiver, FakeMessage(body()), backend=None, runner=None)  # type: ignore[arg-type]
    assert receiver.settled[0][0] == settled
    if action == Action.DEAD_LETTER:
        assert receiver.settled[0][1] == {"reason": "Why", "description": "Because"}


@pytest.mark.parametrize("raw", ["not json", json.dumps({"project_id": "p"}), json.dumps({"project_id": "p", "language": "en", "targets": []})])
async def test_an_invalid_message_is_dead_lettered_without_calling_the_strategy(monkeypatch, raw):
    async def must_not_run(*args, **kwargs):
        raise AssertionError("strategy called for an invalid message")

    monkeypatch.setattr(consumer, "handle_message", must_not_run)
    receiver = FakeReceiver([])
    disposition = await consumer.process_message(receiver, FakeMessage(raw), backend=None, runner=None)  # type: ignore[arg-type]
    assert disposition.reason == "InvalidMessage"
    assert receiver.settled[0][0] == "dead_letter" and receiver.settled[0][1]["reason"] == "InvalidMessage"


async def test_delivery_count_reaches_the_strategy(monkeypatch):
    seen = {}

    async def fake_handle(message, backend, runner, *, delivery_count=1):
        seen["delivery_count"] = delivery_count
        return Disposition(action=Action.COMPLETE)

    monkeypatch.setattr(consumer, "handle_message", fake_handle)
    await consumer.process_message(FakeReceiver([]), FakeMessage(body(), delivery_count=3), None, None)  # type: ignore[arg-type]
    assert seen["delivery_count"] == 3


class FakeRenewer:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.registered: list[int] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def register(self, receiver, msg, max_lock_renewal_duration):
        self.registered.append(max_lock_renewal_duration)


class FakeClient:
    def __init__(self, receiver: FakeReceiver) -> None:
        self._receiver = receiver

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get_queue_receiver(self, **kwargs):
        return self._receiver


class FakeBackend:
    async def aclose(self) -> None:
        pass


async def run_with_lock_setting(monkeypatch, value: str | None) -> tuple[list[int], list[int]]:
    if value is None:
        monkeypatch.delenv("LOCK_RENEWAL_SECONDS", raising=False)
    else:
        monkeypatch.setenv("LOCK_RENEWAL_SECONDS", value)
    monkeypatch.setattr(consumer, "settings", Settings(_env_file=None))

    async def fake_handle(message, backend, runner, *, delivery_count=1):
        return Disposition(action=Action.COMPLETE)

    monkeypatch.setattr(consumer, "handle_message", fake_handle)
    receiver = FakeReceiver([[FakeMessage(body())]])
    renewers: list[FakeRenewer] = []

    def make_renewer(seconds: int) -> FakeRenewer:
        renewers.append(FakeRenewer(seconds))
        return renewers[-1]

    await asyncio.wait_for(
        consumer.run_consumer(
            runner=None,  # type: ignore[arg-type]
            backend=FakeBackend(),  # type: ignore[arg-type]
            client_factory=lambda: FakeClient(receiver),
            renewer_factory=make_renewer,
        ),
        timeout=5,
    )
    return [r.seconds for r in renewers], renewers[0].registered


async def test_lock_renewal_duration_comes_from_the_env_at_both_places(monkeypatch):
    created_with, registered_with = await run_with_lock_setting(monkeypatch, "1234")
    assert created_with == [1234]
    assert registered_with == [1234]


async def test_lock_renewal_defaults_to_900_seconds(monkeypatch):
    created_with, registered_with = await run_with_lock_setting(monkeypatch, None)
    assert created_with == [900] and registered_with == [900]
