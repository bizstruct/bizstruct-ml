"""Shared async retry helper: exponential backoff on a given set of exceptions.

The same shape the generator has always used (`settings.llm_max_retries + 1`
attempts, 2-8 s backoff); extracted so the judge and the stage runner retry the
same way instead of each rolling their own tenacity wrapper.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from bizstruct_ml.config import settings

T = TypeVar("T")


async def retry_async(
    call: Callable[[], Awaitable[T]],
    *,
    retry_on: tuple[type[BaseException], ...],
    attempts: int | None = None,
    wait_min: float = 2.0,
    wait_max: float = 8.0,
) -> T:
    """Await `call()`, retrying on `retry_on`; re-raises the last error.

    `attempts` defaults to `settings.llm_max_retries + 1`.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(attempts if attempts is not None else settings.llm_max_retries + 1),
        wait=wait_exponential(min=wait_min, max=wait_max),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    ):
        with attempt:
            return await call()
    raise AssertionError("unreachable: AsyncRetrying either returns or re-raises")
