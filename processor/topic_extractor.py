import json
import logging

import anthropic

from config import Config
from fetcher.models import Tweet
from processor.models import Topic
from utils.rate_limiter import retry_with_backoff
from utils.usage import UsageTracker

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "あなたはソーシャルメディアのテキスト分析の専門家です。"
    "ツイートを分析し、議論されている主要なトピックを正確に特定します。"
)

_EXTRACT_PROMPT = """\
以下のツイート群を分析し、主要なトピックをJSON配列で返してください。

要件:
- トピックは3〜7個程度に絞ること
- 各トピックには明確な名前と簡潔な説明を付けること
- 類似したテーマはまとめること

出力形式（JSONのみ、他のテキストは不要）:
[
  {{"name": "トピック名", "description": "このトピックの概要（1〜2文）"}},
  ...
]

<tweets>
{tweets_text}
</tweets>
"""


class TopicExtractor:
    def __init__(self, config: Config, tracker: UsageTracker | None = None):
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = config.claude_model
        self._max_retries = config.max_retries
        self._tracker = tracker

    def extract(self, tweets: list[Tweet]) -> list[Topic]:
        """Extract main topics from a list of tweets using Claude."""
        logger.info("Extracting topics from %d tweets", len(tweets))

        tweets_text = "\n".join(
            f"{i + 1}. {tweet.text}" for i, tweet in enumerate(tweets)
        )
        prompt = _EXTRACT_PROMPT.format(tweets_text=tweets_text)

        def _call():
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            if self._tracker:
                self._tracker.add_claude(resp.usage.input_tokens, resp.usage.output_tokens)
            return resp.content[0].text

        response_text = retry_with_backoff(_call, max_retries=self._max_retries)

        topics = self._parse_topics(response_text)
        logger.info("Extracted %d topics", len(topics))
        return topics

    def _parse_topics(self, response_text: str) -> list[Topic]:
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start == -1 or end == 0:
            logger.warning("No JSON array found in response; returning empty topic list")
            return []
        try:
            items = json.loads(response_text[start:end])
            return [Topic(name=item["name"], description=item.get("description", "")) for item in items]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse topics JSON: %s\nRaw: %s", e, response_text)
            return []
