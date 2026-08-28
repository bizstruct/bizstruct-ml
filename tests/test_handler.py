"""Handler tests — all external calls are mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from bizstruct_ml.backend_client import (
    ProjectNotFoundError,
    BackendUnavailableError,
    HookFailedError,
    HookRejectedError,
    HookUnavailableError,
)
from bizstruct_ml.handler import handle_message
from bizstruct_ml.schemas.project import ProjectState


def _make_project(block_value=None, block_name="canvas") -> ProjectState:
    return ProjectState(
        id=uuid4(),
        title="Test Project",
        idea="Test idea",
        status="generating",
        translation_key="en",
        **{block_name: block_value},
    )


def _make_sb_message():
    msg = MagicMock()
    msg.complete_message = AsyncMock()
    msg.abandon_message = AsyncMock()
    msg.dead_letter_message = AsyncMock()
    return msg


def _make_backend(project: ProjectState | None = None, error=None):
    backend = MagicMock()
    if error:
        backend.get_project = AsyncMock(side_effect=error)
    else:
        backend.get_project = AsyncMock(return_value=project)
    backend.send_hook = AsyncMock()
    return backend


def _make_pubsub():
    pubsub = MagicMock()
    pubsub.publish = AsyncMock()
    return pubsub


@pytest.mark.asyncio
async def test_happy_path():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key_partners": []}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    backend.send_hook.assert_awaited_once()
    hook_call = backend.send_hook.call_args[0][0]
    assert hook_call.status == "success"
    assert hook_call.data == {"key_partners": []}
    pubsub.publish.assert_awaited_once()
    sb_msg.complete_message.assert_awaited_once()
    sb_msg.abandon_message.assert_not_called()


@pytest.mark.asyncio
async def test_idempotency_already_generated():
    project = _make_project(block_name="canvas", block_value={"key_partners": []})
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    pubsub = _make_pubsub()

    generator_mock = MagicMock(generate=AsyncMock())
    with patch("bizstruct_ml.handler.GENERATORS", {"canvas": generator_mock}):
        await handle_message(msg, sb_msg, backend, pubsub)

    generator_mock.generate.assert_not_called()
    backend.send_hook.assert_not_called()
    sb_msg.complete_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_bypasses_idempotency():
    """force=True (an explicit regeneration request) generates again even
    though the block already has data — unlike normal chain progression."""
    project = _make_project(block_name="models_options", block_value={"options": []})
    msg = json.dumps({"project_id": str(project.id), "block": "models_options", "force": True})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    pubsub = _make_pubsub()

    generator_mock = MagicMock(generate=AsyncMock(return_value={"options": [], "selected_id": None}))
    with patch("bizstruct_ml.handler.GENERATORS", {"models_options": generator_mock}):
        await handle_message(msg, sb_msg, backend, pubsub)

    generator_mock.generate.assert_awaited_once()
    backend.send_hook.assert_awaited_once()
    sb_msg.complete_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_not_found_dead_letters():
    project_id = str(uuid4())
    msg = json.dumps({"project_id": project_id, "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(error=ProjectNotFoundError("not found"))
    pubsub = _make_pubsub()

    await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.dead_letter_message.assert_awaited_once()
    sb_msg.complete_message.assert_not_called()
    sb_msg.abandon_message.assert_not_called()


@pytest.mark.asyncio
async def test_backend_unavailable_abandons():
    project_id = str(uuid4())
    msg = json.dumps({"project_id": project_id, "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(error=BackendUnavailableError("503"))
    pubsub = _make_pubsub()

    await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.abandon_message.assert_awaited_once()
    sb_msg.complete_message.assert_not_called()
    sb_msg.dead_letter_message.assert_not_called()


@pytest.mark.asyncio
async def test_generation_failed_sends_failed_hook():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(side_effect=Exception("LLM timeout")))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    hook_call = backend.send_hook.call_args[0][0]
    assert hook_call.status == "failed"
    assert "LLM timeout" in hook_call.error
    assert hook_call.data is None
    sb_msg.complete_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_hook_failed_abandons():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(side_effect=HookFailedError("hook down"))
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.abandon_message.assert_awaited_once()
    sb_msg.complete_message.assert_not_called()
    pubsub.publish.assert_not_called()


@pytest.mark.asyncio
async def test_hook_422_dead_letters_without_abandon_or_regeneration():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(
        side_effect=HookRejectedError(
            status_code=422,
            body='{"detail": [{"loc": ["epicenter"], "msg": "invalid"}]}',
            message="Hook rejected with 422",
        )
    )
    pubsub = _make_pubsub()

    generate_mock = AsyncMock(return_value={"key": "val"})
    with patch("bizstruct_ml.handler.GENERATORS", {"canvas": MagicMock(generate=generate_mock)}):
        await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.dead_letter_message.assert_awaited_once()
    sb_msg.abandon_message.assert_not_called()
    sb_msg.complete_message.assert_not_called()
    # A single generation call — a 422 must not trigger any re-generation.
    generate_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_hook_500_abandons_not_dead_lettered():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(side_effect=HookUnavailableError("Hook returned 500"))
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.abandon_message.assert_awaited_once()
    sb_msg.dead_letter_message.assert_not_called()
    sb_msg.complete_message.assert_not_called()


@pytest.mark.asyncio
async def test_hook_timeout_abandons():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(side_effect=HookUnavailableError("Timeout sending hook"))
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.abandon_message.assert_awaited_once()
    sb_msg.dead_letter_message.assert_not_called()


@pytest.mark.asyncio
async def test_hook_404_dead_letters():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(
        side_effect=HookRejectedError(status_code=404, body="Project not found", message="Hook rejected with 404")
    )
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.dead_letter_message.assert_awaited_once()
    sb_msg.abandon_message.assert_not_called()


@pytest.mark.asyncio
async def test_hook_rejected_dead_letter_reason_contains_status_code():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    backend.send_hook = AsyncMock(
        side_effect=HookRejectedError(status_code=422, body="schema violation", message="Hook rejected with 422")
    )
    pubsub = _make_pubsub()

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    _, kwargs = sb_msg.dead_letter_message.call_args
    assert "422" in kwargs["reason"]
    assert "422" in kwargs["error_description"]


@pytest.mark.asyncio
async def test_invalid_json_dead_letters():
    sb_msg = _make_sb_message()
    backend = _make_backend()
    pubsub = _make_pubsub()

    await handle_message("not json {{", sb_msg, backend, pubsub)

    sb_msg.dead_letter_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_block_dead_letters():
    msg = json.dumps({"project_id": str(uuid4()), "block": "nonexistent_block"})
    sb_msg = _make_sb_message()
    backend = _make_backend()
    pubsub = _make_pubsub()

    await handle_message(msg, sb_msg, backend, pubsub)

    sb_msg.dead_letter_message.assert_awaited_once()
    backend.get_project.assert_not_called()


@pytest.mark.asyncio
async def test_pubsub_failure_does_not_prevent_complete():
    project = _make_project(block_name="canvas", block_value=None)
    msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
    sb_msg = _make_sb_message()
    backend = _make_backend(project=project)
    pubsub = _make_pubsub()
    pubsub.publish = AsyncMock(side_effect=Exception("PubSub down"))

    with patch(
        "bizstruct_ml.handler.GENERATORS",
        {"canvas": MagicMock(generate=AsyncMock(return_value={"key": "val"}))},
    ):
        await handle_message(msg, sb_msg, backend, pubsub)

    # pubsub failure is swallowed inside PubSubClient.publish, message still completes
    sb_msg.complete_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_message_completes_with_a_broken_langfuse_client():
    """Full handler flow with tracing 'enabled' but pointed at a client that
    raises on every call — generation must complete exactly as if tracing
    were off."""
    from bizstruct_ml.observability import tracing

    class _ExplodingClient:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError("langfuse down")

        def update_current_span(self, **kwargs):
            raise RuntimeError("langfuse down")

        def flush(self):
            raise RuntimeError("langfuse down")

    tracing._client_init_attempted = True
    tracing._client = _ExplodingClient()
    try:
        project = _make_project(block_name="canvas", block_value=None)
        msg = json.dumps({"project_id": str(project.id), "block": "canvas"})
        sb_msg = _make_sb_message()
        sb_msg.delivery_count = 1
        backend = _make_backend(project=project)
        pubsub = _make_pubsub()

        with patch(
            "bizstruct_ml.handler.GENERATORS",
            {"canvas": MagicMock(generate=AsyncMock(return_value={"key_partners": []}))},
        ):
            await handle_message(msg, sb_msg, backend, pubsub)

        backend.send_hook.assert_awaited_once()
        sb_msg.complete_message.assert_awaited_once()
        sb_msg.abandon_message.assert_not_called()
        sb_msg.dead_letter_message.assert_not_called()
    finally:
        tracing._client = None
        tracing._client_init_attempted = False
