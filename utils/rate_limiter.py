import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

import anthropic
import tweepy

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(func: Callable[[], T], max_retries: int = 5) -> T:
    """Call func, retrying on rate-limit errors with jittered exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (anthropic.RateLimitError, tweepy.TooManyRequests) as e:
            if attempt == max_retries:
                logger.error("Max retries (%d) reached. Giving up.", max_retries)
                raise
            wait = min(60.0, 2 ** attempt + random.uniform(0, 1))
            logger.warning(
                "Rate limited (%s). Retrying in %.1fs (attempt %d/%d)...",
                type(e).__name__,
                wait,
                attempt + 1,
                max_retries,
            )
            time.sleep(wait)
    # Should never reach here
    raise RuntimeError("retry_with_backoff: unexpected exit")


async def async_retry_with_backoff(
    coro_func: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 5,
    retriable_exceptions: tuple[type[Exception], ...] = (),
) -> T:
    """
    Call coro_func(), retrying on retriable_exceptions with jittered
    exponential backoff. Designed for use with ccxt async calls.

    Example:
        import ccxt
        ticker = await async_retry_with_backoff(
            lambda: exchange.fetch_ticker("BTC/USDT"),
            retriable_exceptions=(ccxt.RateLimitExceeded, ccxt.NetworkError),
        )
    """
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except retriable_exceptions as e:
            if attempt == max_retries:
                logger.error("Max retries (%d) reached. Giving up.", max_retries)
                raise
            wait = min(60.0, 2**attempt + random.uniform(0, 1))
            logger.warning(
                "Retriable error (%s). Retrying in %.1fs (attempt %d/%d)...",
                type(e).__name__,
                wait,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait)
    raise RuntimeError("async_retry_with_backoff: unexpected exit")
