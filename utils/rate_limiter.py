import logging
import random
import time
from typing import Callable, TypeVar

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
