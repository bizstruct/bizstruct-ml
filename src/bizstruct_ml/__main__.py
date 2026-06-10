import asyncio
import logging

import structlog

from bizstruct_ml.config import settings


def _configure_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def main() -> None:
    _configure_logging()
    from bizstruct_ml.consumer import run_consumer
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
