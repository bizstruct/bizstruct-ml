import asyncio
import logging
import sys

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
    from bizstruct_ml.adapters.consumer import run_consumer
    from bizstruct_ml.strategies.pipeline import build_runner

    log = structlog.get_logger()
    try:
        # Validate configuration (judge settings, generator/judge family guard)
        # before touching the queue: a misconfigured worker must not start.
        runner = build_runner(settings)
    except Exception as e:
        log.error("startup_refused", error=str(e), error_type=type(e).__name__)
        sys.exit(1)
    asyncio.run(run_consumer(runner))


if __name__ == "__main__":
    main()
