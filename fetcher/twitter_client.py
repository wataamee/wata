import logging
from datetime import datetime, timezone

import tweepy

from config import Config
from fetcher.models import Tweet

logger = logging.getLogger(__name__)


class TwitterClient:
    def __init__(self, config: Config):
        self._client = tweepy.Client(
            bearer_token=config.x_bearer_token,
            wait_on_rate_limit=True,
        )

    def search_recent(self, query: str, max_results: int = 100) -> list[Tweet]:
        """Search recent tweets (last 7 days) for the given query."""
        logger.info("Searching tweets: query=%r max_results=%d", query, max_results)
        tweets: list[Tweet] = []

        # Exclude retweets unless the caller already has that in query
        if "-is:retweet" not in query:
            query = f"{query} -is:retweet"

        try:
            for tweet in tweepy.Paginator(
                self._client.search_recent_tweets,
                query=query,
                tweet_fields=["created_at", "author_id", "text"],
                max_results=min(100, max_results),
            ).flatten(limit=max_results):
                tweets.append(
                    Tweet(
                        id=str(tweet.id),
                        text=tweet.text,
                        author_id=str(tweet.author_id),
                        created_at=tweet.created_at or datetime.now(tz=timezone.utc),
                        url=f"https://x.com/i/web/status/{tweet.id}",
                    )
                )
        except tweepy.TweepyException as e:
            logger.error("Failed to fetch tweets: %s", e)
            raise

        logger.info("Fetched %d tweets", len(tweets))
        return tweets
