import asyncio
import json
import signal
from collections.abc import Callable
from typing import Any

import structlog
from azure.servicebus.aio import AutoLockRenewer, ServiceBusClient
from bizstruct_domain.schemas import QueueMessage
from pydantic import ValidationError

from bizstruct_ml.adapters.backend_client import BackendClient
from bizstruct_ml.config import settings
from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.strategies.pipeline import Action, Disposition, handle_message

log = structlog.get_logger()

_shutdown = asyncio.Event()


def _request_shutdown(*_: object) -> None:
    log.info("shutdown_requested")
    _shutdown.set()


async def process_message(receiver: Any, msg: Any, backend: BackendClient, runner: StageRunner) -> Disposition:
    """Parse one Service Bus message, run the pipeline strategy, settle the message."""
    try:
        queue_message = QueueMessage.model_validate(json.loads(str(msg)))
    except (json.JSONDecodeError, ValidationError) as e:
        log.error("message_dead_lettered", reason="invalid_message", error=str(e))
        disposition = Disposition(action=Action.DEAD_LETTER, reason="InvalidMessage", description=str(e))
    else:
        delivery_count = getattr(msg, "delivery_count", 1) or 1
        disposition = await handle_message(queue_message, backend, runner, delivery_count=delivery_count)

    if disposition.action == Action.COMPLETE:
        await receiver.complete_message(msg)
    elif disposition.action == Action.ABANDON:
        await receiver.abandon_message(msg)
    else:
        await receiver.dead_letter_message(
            msg, reason=disposition.reason, error_description=disposition.description
        )
    return disposition


async def run_consumer(
    runner: StageRunner,
    *,
    backend: BackendClient | None = None,
    client_factory: Callable[[], Any] | None = None,
    renewer_factory: Callable[[int], Any] | None = None,
) -> None:
    """Consume the queue until shutdown. The factories exist so tests can fake Service Bus."""
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _request_shutdown)
    loop.add_signal_handler(signal.SIGINT, _request_shutdown)

    backend = backend or BackendClient()
    lock_seconds = settings.lock_renewal_seconds
    make_client = client_factory or (
        lambda: ServiceBusClient.from_connection_string(settings.service_bus_connection_string, logging_enable=False)
    )
    make_renewer = renewer_factory or (lambda seconds: AutoLockRenewer(max_lock_renewal_duration=seconds))

    log.info("consumer_starting", queue=settings.service_bus_queue_name, lock_renewal_seconds=lock_seconds)

    async with make_client() as sb_client:
        async with sb_client.get_queue_receiver(
            queue_name=settings.service_bus_queue_name,
            prefetch_count=0,
        ) as receiver:
            async with make_renewer(lock_seconds) as renewer:
                log.info("consumer_ready")
                while not _shutdown.is_set():
                    messages = await receiver.receive_messages(max_message_count=1, max_wait_time=5)
                    for msg in messages:
                        renewer.register(receiver, msg, max_lock_renewal_duration=lock_seconds)
                        await process_message(receiver, msg, backend, runner)

    await backend.aclose()
    log.info("consumer_stopped")
