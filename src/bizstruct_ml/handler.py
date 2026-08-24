import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from bizstruct_ml.backend_client import BackendClient, ProjectNotFoundError, BackendUnavailableError, HookFailedError
from bizstruct_ml.generators.registry import GENERATORS
from bizstruct_ml.generators.validate_model import run_validate_model
from bizstruct_ml.llm.client import LLMError
from bizstruct_ml.pubsub_client import PubSubClient
from bizstruct_ml.schemas.messages import HookPayload, QueueMessage, KNOWN_BLOCKS

log = structlog.get_logger()


async def handle_message(
    raw_body: str,
    sb_message: Any,
    backend: BackendClient,
    pubsub: PubSubClient,
) -> None:
    # Step 1: parse message
    try:
        data = json.loads(raw_body)
        msg = QueueMessage.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        log.error("message_dead_lettered", reason="invalid_message", error=str(e))
        await sb_message.dead_letter_message(
            sb_message,
            reason="InvalidMessage",
            error_description=str(e),
        )
        return

    project_id = str(msg.project_id)
    block = msg.block
    bound_log = log.bind(project_id=project_id, block=block)

    if block not in KNOWN_BLOCKS:
        bound_log.error("message_dead_lettered", reason="unknown_block")
        await sb_message.dead_letter_message(
            sb_message,
            reason="UnknownBlock",
            error_description=f"Unknown block: {block}",
        )
        return

    bound_log.info("message_received")

    # validate_model is a special non-generation block handled separately
    if block == "validate_model":
        await _handle_validate_model(msg, sb_message, backend, bound_log)
        return

    # Step 2: fetch project
    try:
        project = await backend.get_project(project_id)
    except ProjectNotFoundError:
        bound_log.error("message_dead_lettered", reason="project_not_found")
        await sb_message.dead_letter_message(
            sb_message,
            reason="ProjectNotFound",
            error_description=f"Project {project_id} does not exist",
        )
        return
    except BackendUnavailableError as e:
        bound_log.warning("message_abandoned", reason="backend_unavailable", error=str(e))
        await sb_message.abandon_message(sb_message)
        return

    # Step 3: idempotency check
    if project.get_block(block) is not None:
        bound_log.info("already_generated")
        await sb_message.complete_message(sb_message)
        return

    # Step 4: generate
    bound_log.info("generation_started")
    start = time.monotonic()
    generation_error: str | None = None
    result_data: dict | None = None

    try:
        generator = GENERATORS[block]
        result_data = await generator.generate(project)
        duration = time.monotonic() - start
        bound_log.info("generation_succeeded", duration_s=round(duration, 2))
    except (LLMError, ValidationError, Exception) as e:
        duration = time.monotonic() - start
        generation_error = str(e)
        bound_log.error("generation_failed", error=generation_error, duration_s=round(duration, 2))

    # Steps 5/6: send hook
    hook_status = "success" if result_data is not None else "failed"
    hook = HookPayload(
        project_id=msg.project_id,
        block=block,
        status=hook_status,  # type: ignore[arg-type]
        data=result_data,
        error=generation_error,
    )

    try:
        await backend.send_hook(hook)
        bound_log.info("hook_sent", status=hook_status)
    except HookFailedError as e:
        bound_log.error("hook_failed", error=str(e))
        await sb_message.abandon_message(sb_message)
        return

    # Notify frontend via PubSub — failure must not block completion
    try:
        await pubsub.publish(project_id, block, hook_status)
        bound_log.info("pubsub_published", status=hook_status)
    except Exception as exc:
        bound_log.warning("pubsub_publish_failed", error=str(exc))

    await sb_message.complete_message(sb_message)
    bound_log.info("message_completed")


async def _handle_validate_model(
    msg: QueueMessage,
    sb_message: Any,
    backend: BackendClient,
    bound_log: Any,
) -> None:
    project_id = str(msg.project_id)
    payload = msg.payload or {}
    model_id = payload.get("model_id", "")

    bound_log.info("validate_model_started", model_id=model_id)
    start = time.monotonic()

    error: str | None = None
    result_data: dict | None = None
    try:
        result_data = await run_validate_model(payload)
        bound_log.info("validate_model_succeeded", duration_s=round(time.monotonic() - start, 2))
    except (LLMError, ValidationError, Exception) as e:
        error = str(e)
        bound_log.error("validate_model_failed", error=error, duration_s=round(time.monotonic() - start, 2))

    hook_status = "success" if result_data is not None else "failed"
    hook = HookPayload(
        project_id=msg.project_id,
        block="validate_model",
        status=hook_status,  # type: ignore[arg-type]
        data=result_data,
        error=error,
    )

    try:
        await backend.send_hook(hook)
        bound_log.info("validate_hook_sent", status=hook_status)
    except HookFailedError as e:
        bound_log.error("validate_hook_failed", error=str(e))
        await sb_message.abandon_message(sb_message)
        return

    await sb_message.complete_message(sb_message)
    bound_log.info("validate_model_completed")
