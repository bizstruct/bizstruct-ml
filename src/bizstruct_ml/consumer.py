import asyncio
import signal

import structlog
from azure.servicebus.aio import ServiceBusClient, AutoLockRenewer
from azure.servicebus import ServiceBusMessage

from bizstruct_ml.backend_client import BackendClient
from bizstruct_ml.config import settings
from bizstruct_ml.handler import handle_message
from bizstruct_ml.pubsub_client import PubSubClient

log = structlog.get_logger()

_shutdown = asyncio.Event()


def _request_shutdown(*_: object) -> None:
    log.info("shutdown_requested")
    _shutdown.set()


class _SBMessageAdapter:
    """Adapts ServiceBusReceiver methods to the interface expected by handle_message."""

    def __init__(self, receiver: object, msg: object) -> None:
        self._receiver = receiver
        self._msg = msg

    async def complete_message(self, _: object) -> None:
        await self._receiver.complete_message(self._msg)  # type: ignore[attr-defined]

    async def abandon_message(self, _: object) -> None:
        await self._receiver.abandon_message(self._msg)  # type: ignore[attr-defined]

    async def dead_letter_message(
        self,
        _: object,
        reason: str = "",
        error_description: str = "",
    ) -> None:
        await self._receiver.dead_letter_message(  # type: ignore[attr-defined]
            self._msg,
            reason=reason,
            error_description=error_description,
        )


async def run_consumer() -> None:
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _request_shutdown)
    loop.add_signal_handler(signal.SIGINT, _request_shutdown)

    backend = BackendClient()
    pubsub = PubSubClient()

    log.info("consumer_starting", queue=settings.service_bus_queue_name)

    async with ServiceBusClient.from_connection_string(
        settings.service_bus_connection_string,
        logging_enable=False,
    ) as sb_client:
        async with sb_client.get_queue_receiver(
            queue_name=settings.service_bus_queue_name,
            prefetch_count=0,
        ) as receiver:
            async with AutoLockRenewer(max_lock_renewal_duration=300) as renewer:
                log.info("consumer_ready")
                while not _shutdown.is_set():
                    messages = await receiver.receive_messages(
                        max_message_count=1,
                        max_wait_time=5,
                    )
                    for msg in messages:
                        renewer.register(receiver, msg, max_lock_renewal_duration=300)
                        adapter = _SBMessageAdapter(receiver, msg)
                        raw = str(msg)
                        await handle_message(raw, adapter, backend, pubsub)

    await backend.aclose()
    log.info("consumer_stopped")
