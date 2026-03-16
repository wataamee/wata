import json
import logging

import anthropic

from config import Config
from fetcher.models import Tweet
from processor.models import Topic, TweetGroup
from utils.rate_limiter import retry_with_backoff
from utils.usage import UsageTracker

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "あなたはテキスト分類の専門家です。"
    "ツイートを与えられたトピックリストのうち最も関連性の高いものに分類します。"
)

_GROUP_PROMPT = """\
以下のツイートを、与えられたトピックリストのいずれかに分類してください。

トピックリスト:
{topics_text}

要件:
- 各ツイートを最も関連性の高いトピックに1つだけ割り当てること
- どのトピックにも当てはまらない場合は "other" を使うこと
- JSON形式のみで返すこと（他のテキスト不要）

出力形式:
{{"assignments": [{{"tweet_index": 0, "topic_name": "トピック名"}}, ...]}}

<tweets>
{tweets_text}
</tweets>
"""


class TweetGrouper:
    def __init__(self, config: Config, tracker: UsageTracker | None = None):
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = config.claude_model
        self._max_retries = config.max_retries
        self._tracker = tracker

    def group(self, tweets: list[Tweet], topics: list[Topic]) -> list[TweetGroup]:
        """Assign each tweet to a topic and return grouped TweetGroup objects."""
        if not topics:
            logger.warning("No topics provided; skipping grouping")
            return []

        logger.info("Grouping %d tweets into %d topics", len(tweets), len(topics))

        topics_text = "\n".join(
            f"- {t.name}: {t.description}" for t in topics
        )
        tweets_text = "\n".join(
            f"{i}. {tweet.text}" for i, tweet in enumerate(tweets)
        )
        prompt = _GROUP_PROMPT.format(topics_text=topics_text, tweets_text=tweets_text)

        def _call():
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            if self._tracker:
                self._tracker.add_claude(resp.usage.input_tokens, resp.usage.output_tokens)
            return resp.content[0].text

        response_text = retry_with_backoff(_call, max_retries=self._max_retries)

        return self._build_groups(tweets, topics, response_text)

    def _build_groups(
        self, tweets: list[Tweet], topics: list[Topic], response_text: str
    ) -> list[TweetGroup]:
        # Parse assignments from Claude's response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        assignments: dict[str, list[Tweet]] = {}

        if start != -1 and end > 0:
            try:
                data = json.loads(response_text[start:end])
                for item in data.get("assignments", []):
                    idx = item.get("tweet_index")
                    topic_name = item.get("topic_name", "other")
                    if idx is not None and 0 <= idx < len(tweets):
                        assignments.setdefault(topic_name, []).append(tweets[idx])
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to parse grouping JSON: %s\nRaw: %s", e, response_text)

        topic_map = {t.name: t for t in topics}
        groups: list[TweetGroup] = []
        for topic_name, group_tweets in assignments.items():
            if not group_tweets:
                continue
            topic = topic_map.get(topic_name, Topic(name=topic_name, description=""))
            groups.append(TweetGroup(topic=topic, tweets=group_tweets))

        logger.info("Created %d tweet groups", len(groups))
        return groups
