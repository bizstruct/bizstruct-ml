"""Optional Langfuse tracing for the generation pipeline.

Disabled by default: without LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set,
every function here is a no-op — the worker must behave identically with or
without Langfuse configured, since it's a stateless queue worker that can't
be allowed to fail because an observability backend is unreachable.

Every call into the Langfuse SDK is isolated behind a try/except that logs a
warning and continues. The one thing these wrappers must NEVER do is swallow
an exception raised by the caller's own code inside a `with tracing.span(...)`
block — that would silently break retry logic and error handling elsewhere.
See `_guarded()`.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Any, Iterator

import structlog

from bizstruct_ml.config import settings

log = structlog.get_logger()


class _NoOpObservation:
    """Stand-in for a Langfuse span/generation when tracing is disabled, or
    a tracing call itself failed. Same `.update()` interface, does nothing —
    callers don't need to branch on whether tracing is actually active."""

    def update(self, **_kwargs: Any) -> "_NoOpObservation":
        return self


NOOP = _NoOpObservation()

_client: Any = None
_client_init_attempted = False


def _get_client() -> Any:
    """Lazily construct the Langfuse client. Returns None if tracing isn't
    configured, or if the SDK failed to import/construct — either way, the
    caller must treat None as "tracing is off", not raise."""
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True

    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        log.warning("langfuse_init_failed", exc_info=True)
        _client = None
    return _client


@contextlib.contextmanager
def _guarded(label: str, cm_factory: Any) -> Iterator[Any]:
    """Safely enter/exit a context manager Langfuse gives us.

    `cm_factory` is a zero-arg callable returning a context manager, or None
    if there's nothing to enter (tracing disabled/unavailable). Failure to
    enter or exit is logged and degrades to NOOP — but any exception raised
    by the code running *inside* the `with` block (the caller's own logic)
    is always re-raised untouched; this must never be mistaken for a
    tracing failure.
    """
    cm = None
    obs: Any = NOOP
    if cm_factory is not None:
        try:
            cm = cm_factory()
            obs = cm.__enter__()
        except Exception:
            log.warning("langfuse_enter_failed", target=label, exc_info=True)
            cm = None
            obs = NOOP

    try:
        yield obs
    except BaseException:
        if cm is not None:
            try:
                cm.__exit__(*sys.exc_info())
            except Exception:
                log.warning("langfuse_exit_failed", target=label, exc_info=True)
        raise
    else:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                log.warning("langfuse_exit_failed", target=label, exc_info=True)


@contextlib.contextmanager
def trace_block_generation(
    *,
    project_id: str,
    block: str,
    mode: str,
    attempt_number: int,
    domain_version: str,
) -> Iterator[Any]:
    """Root span for processing one queue message end to end.

    Yields the root observation (or NOOP) so callers can attach a final
    outcome/retry-count via `.update(...)` once processing finishes. Every
    span opened anywhere else in the pipeline while this context is active
    (via tracing.span / tracing.generation_span) nests under it, and
    inherits session_id/tags/metadata via propagate_attributes — no need to
    thread span objects through function signatures.
    """
    client = _get_client()
    if client is None:
        yield NOOP
        return

    root_factory = lambda: client.start_as_current_observation(  # noqa: E731
        name="generate_block", as_type="span"
    )
    with _guarded("generate_block", root_factory) as root:
        prop_factory = None
        try:
            from langfuse import propagate_attributes

            prop_factory = lambda: propagate_attributes(  # noqa: E731
                session_id=project_id,
                tags=[block, mode],
                trace_name="generate_block",
                metadata={
                    "project_id": project_id,
                    "block": block,
                    "attempt_number": attempt_number,
                    "bizstruct_domain_version": domain_version,
                },
            )
        except Exception:
            log.warning("langfuse_propagate_import_failed", exc_info=True)

        with _guarded("propagate_attributes", prop_factory):
            yield root


@contextlib.contextmanager
def span(name: str, **kwargs: Any) -> Iterator[Any]:
    """A plain child span, nested under whatever's currently active."""
    client = _get_client()
    factory = None
    if client is not None:
        factory = lambda: client.start_as_current_observation(  # noqa: E731
            name=name, as_type="span", **kwargs
        )
    with _guarded(name, factory) as obs:
        yield obs


@contextlib.contextmanager
def generation_span(name: str, **kwargs: Any) -> Iterator[Any]:
    """A generation-type child span (model, usage, cost tracked by Langfuse)."""
    client = _get_client()
    factory = None
    if client is not None:
        factory = lambda: client.start_as_current_observation(  # noqa: E731
            name=name, as_type="generation", **kwargs
        )
    with _guarded(name, factory) as obs:
        yield obs


def update_current_span(**kwargs: Any) -> None:
    """Update whatever observation is currently active (e.g. attach a final
    retry count or outcome to the root span after child spans have closed).
    No-op if tracing is disabled or the call fails."""
    client = _get_client()
    if client is None:
        return
    try:
        client.update_current_span(**kwargs)
    except Exception:
        log.warning("langfuse_update_current_span_failed", exc_info=True)


def flush() -> None:
    """Best-effort flush of any buffered trace data. Never raises."""
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        log.warning("langfuse_flush_failed", exc_info=True)


async def aflush() -> None:
    """Async wrapper around flush() — the Langfuse client's flush() is a
    blocking HTTP call; offload it so it doesn't stall the event loop.
    No-op (returns immediately) if tracing is disabled."""
    if _get_client() is None:
        return
    try:
        await asyncio.to_thread(flush)
    except Exception:
        log.warning("langfuse_aflush_failed", exc_info=True)
