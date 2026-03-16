import logging

import anthropic

from config import Config
from processor.models import TweetGroup
from utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "あなたは優れたジャーナリストです。"
    "ソーシャルメディアの投稿をもとに、読みやすく情報量の多いレポート記事を日本語で書きます。"
    "客観的な視点を保ち、ツイートの内容を忠実に反映させてください。"
)

_ARTICLE_PROMPT = """\
以下のツイートをもとに、「{topic_name}」についての日本語Markdownレポート記事を書いてください。

トピックの説明: {topic_description}

要件:
- 導入段落（このトピックの概要）
- 主要な論点・観点ごとにH2見出しを使ったセクション（2〜4個）
- 各セクションでは関連するツイートの内容を引用・言及すること
- まとめセクション（Key Takeaways）
- 全体で400〜600字程度

<tweets>
{tweets_text}
</tweets>
"""


class ArticleWriter:
    def __init__(self, config: Config):
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = config.claude_model
        self._max_retries = config.max_retries

    def generate(self, group: TweetGroup) -> str:
        """Generate a Markdown article for a TweetGroup."""
        logger.info(
            "Generating article for topic=%r (%d tweets)",
            group.topic.name,
            len(group.tweets),
        )

        tweets_text = "\n".join(
            f"- {tweet.text} ({tweet.url})" for tweet in group.tweets
        )
        prompt = _ARTICLE_PROMPT.format(
            topic_name=group.topic.name,
            topic_description=group.topic.description,
            tweets_text=tweets_text,
        )

        article = retry_with_backoff(
            lambda: self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ).content[0].text,
            max_retries=self._max_retries,
        )

        logger.info("Article generated for topic=%r", group.topic.name)
        return article
