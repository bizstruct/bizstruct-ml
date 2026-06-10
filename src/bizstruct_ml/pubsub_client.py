import asyncio
import structlog

from bizstruct_ml.config import settings
from bizstruct_ml.schemas.messages import PubSubEvent

log = structlog.get_logger()


class PubSubClient:
    def __init__(self) -> None:
        if settings.webpubsub_connection_string:
            from azure.messaging.webpubsubservice import WebPubSubServiceClient
            self._client = WebPubSubServiceClient.from_connection_string(
                settings.webpubsub_connection_string,
                hub=settings.webpubsub_hub,
            )
        else:
            self._client = None
            log.warning("pubsub_not_configured", reason="WEBPUBSUB_CONNECTION_STRING not set")

    async def publish(self, project_id: str, block: str, status: str) -> None:
        if self._client is None:
            return
        event = PubSubEvent(project_id=project_id, block=block, status=status)  # type: ignore[arg-type]
        group = f"project:{project_id}"
        try:
            await asyncio.to_thread(
                self._client.send_to_group,
                group,
                event.model_dump_json(),
                content_type="application/json",
            )
        except Exception as e:
            log.warning(
                "pubsub_publish_failed",
                project_id=project_id,
                block=block,
                error=str(e),
            )
