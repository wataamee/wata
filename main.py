#!/usr/bin/env python3
"""
main.py — X (Twitter) トピック抽出 & 記事生成ツール

使い方:
    python main.py --query "AI 生成" --max-tweets 50
"""
import argparse
import logging
import sys

from config import load_config
from fetcher.twitter_client import TwitterClient
from generator.article_writer import ArticleWriter
from processor.topic_extractor import TopicExtractor
from processor.tweet_grouper import TweetGrouper
from utils.file_writer import save_article
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Xのツイートからトピックを抽出し、まとめ記事を生成します"
    )
    parser.add_argument(
        "--query",
        required=True,
        help='検索クエリ（例: "AI 生成 -is:retweet lang:ja"）',
    )
    parser.add_argument(
        "--max-tweets",
        type=int,
        default=None,
        metavar="N",
        help="取得するツイートの最大数（デフォルト: 設定ファイルの MAX_TWEETS）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="記事の出力先ディレクトリ（デフォルト: 設定ファイルの OUTPUT_DIR）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="詳細ログを表示する"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    try:
        config = load_config()
    except EnvironmentError as e:
        logger.error("%s", e)
        return 1

    # CLI args override config values when provided
    max_tweets = args.max_tweets if args.max_tweets is not None else config.max_tweets
    output_dir = args.output_dir if args.output_dir is not None else config.output_dir

    # ── 1. ツイート取得 ────────────────────────────────────────────────
    twitter = TwitterClient(config)
    try:
        tweets = twitter.search_recent(args.query, max_results=max_tweets)
    except Exception as e:
        logger.error("ツイートの取得に失敗しました: %s", e)
        return 1

    if not tweets:
        logger.warning("クエリ %r に一致するツイートが見つかりませんでした", args.query)
        return 0

    # ── 2. トピック抽出 ───────────────────────────────────────────────
    extractor = TopicExtractor(config)
    try:
        topics = extractor.extract(tweets)
    except Exception as e:
        logger.error("トピック抽出に失敗しました: %s", e)
        return 1

    if not topics:
        logger.warning("トピックを抽出できませんでした")
        return 0

    print(f"\n抽出されたトピック ({len(topics)}件):")
    for t in topics:
        print(f"  • {t.name}: {t.description}")

    # ── 3. ツイートをトピックにグループ化 ────────────────────────────
    grouper = TweetGrouper(config)
    try:
        groups = grouper.group(tweets, topics)
    except Exception as e:
        logger.error("グループ化に失敗しました: %s", e)
        return 1

    if not groups:
        logger.warning("有効なツイートグループを作成できませんでした")
        return 0

    # ── 4. 各トピックの記事を生成・保存 ──────────────────────────────
    writer = ArticleWriter(config)
    saved_paths = []

    for group in groups:
        try:
            markdown = writer.generate(group)
            path = save_article(group.topic.name, markdown, output_dir)
            saved_paths.append(path)
        except Exception as e:
            logger.error("トピック %r の記事生成に失敗しました: %s", group.topic.name, e)

    # ── 結果サマリー ──────────────────────────────────────────────────
    print(f"\n生成完了: {len(saved_paths)} 件の記事を {output_dir}/ に保存しました")
    for p in saved_paths:
        print(f"  {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
