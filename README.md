# wata — X トピック抽出 & 記事生成ツール

Xのツイートから特定の話題を自動的に抽出し、Claude APIを使ってその話題ごとにまとめ記事（Markdown）を生成するPythonツールです。

## 動作フロー

```
[1] X API でツイートを取得
        ↓
[2] Claude でトピックを抽出
        ↓
[3] Claude で各ツイートをトピックに分類
        ↓
[4] Claude でトピックごとに記事を生成
        ↓
[5] output/<topic>.md として保存
```

## セットアップ

### 必要なもの

- Python 3.11+
- X Developer アカウント（Bearer Token）
- Anthropic API キー

### インストール

```bash
pip install -r requirements.txt
```

### 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集して API キーを設定します:

```
X_BEARER_TOKEN=your_bearer_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## 使い方

```bash
# 基本的な使い方
python main.py --query "AI 生成"

# ツイート数と出力先を指定
python main.py --query "生成AI -is:retweet lang:ja" --max-tweets 50 --output-dir articles

# 詳細ログを表示
python main.py --query "LLM" --verbose
```

### オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--query` | (必須) | X の検索クエリ |
| `--max-tweets` | 100 | 取得するツイートの最大数 |
| `--output-dir` | `output/` | 記事の出力先ディレクトリ |
| `--verbose` | false | 詳細ログを表示 |

### 検索クエリの例

```
"Python 機械学習 -is:retweet lang:ja"
"ChatGPT site:techcrunch.com"
"#生成AI -is:retweet lang:ja"
```

X API v2 の [検索クエリ構文](https://developer.x.com/en/docs/twitter-api/tweets/search/integrate/build-a-query) を参照してください。

## 出力例

```
抽出されたトピック (4件):
  • AI活用事例: 企業や個人によるAIツールの実際の活用事例
  • 技術解説: LLMや生成AIの仕組みに関する技術的な解説
  • 規制・倫理: AIに関する法規制や倫理的議論
  • ツール比較: 各種AIツール・サービスの比較・評価

生成完了: 4 件の記事を output/ に保存しました
  output/ai活用事例.md
  output/技術解説.md
  output/規制・倫理.md
  output/ツール比較.md
```

## 環境変数一覧

| 変数名 | 必須 | デフォルト | 説明 |
|-------|------|-----------|------|
| `X_BEARER_TOKEN` | ✓ | — | X API v2 Bearer Token |
| `ANTHROPIC_API_KEY` | ✓ | — | Anthropic API キー |
| `CLAUDE_MODEL` | | `claude-opus-4-5` | 使用する Claude モデル |
| `MAX_TWEETS` | | `100` | 取得ツイート数の上限 |
| `OUTPUT_DIR` | | `output` | 記事の出力先 |
| `MAX_RETRIES` | | `5` | APIレートリミット時の最大リトライ回数 |

## プロジェクト構造

```
wata/
├── main.py                    # CLIエントリポイント
├── config.py                  # 設定管理
├── requirements.txt
├── .env.example
├── fetcher/
│   ├── twitter_client.py      # X APIクライアント
│   └── models.py              # Tweet dataclass
├── processor/
│   ├── topic_extractor.py     # トピック抽出（Claude）
│   ├── tweet_grouper.py       # ツイートのグループ化（Claude）
│   └── models.py              # Topic/TweetGroup dataclass
├── generator/
│   └── article_writer.py      # 記事生成（Claude）
└── utils/
    ├── rate_limiter.py        # リトライ・バックオフ
    ├── file_writer.py         # ファイル保存
    └── logger.py              # ロギング設定
```
