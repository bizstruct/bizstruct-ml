import json
import time
from typing import Any

import bizstruct_domain
import structlog
from pydantic import ValidationError

from bizstruct_ml.backend_client import (
    BackendClient,
    BackendUnavailableError,
    HookFailedError,
    HookRejectedError,
    ProjectNotFoundError,
)
from bizstruct_ml.generators.registry import GENERATORS
from bizstruct_ml.generators.validate_model import run_validate_model
from bizstruct_ml.llm.client import LLMError
from bizstruct_ml.observability import tracing
from bizstruct_ml.pubsub_client import PubSubClient
from bizstruct_ml.schemas.messages import HookPayload, QueueMessage, KNOWN_BLOCKS

log = structlog.get_logger()


async def _send_hook(
    backend: BackendClient,
    hook: HookPayload,
    sb_message: Any,
    bound_log: Any,
    log_prefix: str,
) -> bool:
    """Send the hook and settle the queue message on failure.

    Returns True if the hook was accepted (caller should proceed to
    complete_message). Returns False if this function already settled the
    message (dead-lettered a rejected payload, or abandoned a transient
    failure) — the caller must return immediately without completing.
    """
    with tracing.span("send_hook") as hook_span:
        try:
            await backend.send_hook(hook)
            hook_span.update(output={"status_code": 200})
            bound_log.info(f"{log_prefix}_sent", status=hook.status)
            return True
        except HookRejectedError as e:
            # The backend has definitively rejected this payload (422 schema
            # violation, 404 project gone, any other 4xx). Retrying would
            # regenerate/resend the exact same rejected content — dead-letter
            # immediately instead of burning through the queue's retry budget.
            hook_span.update(output={"status_code": e.status_code, "outcome": "dead_letter"})
            bound_log.error(
                f"{log_prefix}_rejected",
                status_code=e.status_code,
                body=e.body,
            )
            await sb_message.dead_letter_message(
                sb_message,
                reason=f"HookRejected_{e.status_code}",
                error_description=f"HTTP {e.status_code}: {e.body}",
            )
            return False
        except HookFailedError as e:
            # HookUnavailableError (5xx, timeout, network error) and anything
            # else uncategorized: the backend, or the network to it, is having a
            # bad time — worth abandoning so the queue redelivers.
            hook_span.update(output={"outcome": "abandon", "error": str(e)})
            bound_log.warning(f"{log_prefix}_failed", error=str(e))
            await sb_message.abandon_message(sb_message)
            return False


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

    attempt_number = getattr(sb_message, "delivery_count", 1) or 1

    with tracing.trace_block_generation(
        project_id=project_id,
        block=block,
        mode="pipeline",
        attempt_number=attempt_number,
        domain_version=bizstruct_domain.__version__,
    ) as root_span:
        try:
            await _process_block(msg, sb_message, backend, pubsub, bound_log, project_id, block, root_span)
        finally:
            await tracing.aflush()


async def _process_block(
    msg: QueueMessage,
    sb_message: Any,
    backend: BackendClient,
    pubsub: PubSubClient,
    bound_log: Any,
    project_id: str,
    block: str,
    root_span: Any,
) -> None:
    # Step 2: fetch project
    with tracing.span("fetch_project"):
        try:
            project = await backend.get_project(project_id)
        except ProjectNotFoundError:
            bound_log.error("message_dead_lettered", reason="project_not_found")
            root_span.update(output={"outcome": "dead_letter", "reason": "project_not_found"})
            await sb_message.dead_letter_message(
                sb_message,
                reason="ProjectNotFound",
                error_description=f"Project {project_id} does not exist",
            )
            return
        except BackendUnavailableError as e:
            bound_log.warning("message_abandoned", reason="backend_unavailable", error=str(e))
            root_span.update(output={"outcome": "abandon", "reason": "backend_unavailable"})
            await sb_message.abandon_message(sb_message)
            return

    # Step 3: idempotency check — bypassed when the message is an explicit
    # regeneration request (msg.force=True), e.g. models_options' "regenerate"
    # action. Normal chain progression always has force=False, so this is
    # unchanged for every other block.
    if not msg.force and project.get_block(block) is not None:
        bound_log.info("already_generated")
        root_span.update(output={"outcome": "already_generated"})
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

    if not await _send_hook(backend, hook, sb_message, bound_log, "hook"):
        # _send_hook already recorded the outcome (dead_letter/abandon) on
        # the send_hook span; nothing further to attach at the root here.
        return

    if generation_error is not None:
        root_span.update(output={"outcome": "failed_hook_sent", "error": generation_error})
    else:
        root_span.update(output={"outcome": "success"})

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

    if not await _send_hook(backend, hook, sb_message, bound_log, "validate_hook"):
        return

    await sb_message.complete_message(sb_message)
    bound_log.info("validate_model_completed")
