from dataclasses import dataclass

# Claude pricing (per 1M tokens) — claude-opus-4-5
_INPUT_COST_PER_M  = 15.0   # USD
_OUTPUT_COST_PER_M = 75.0   # USD

# X API v2 は 2026年2月より従量課金制（Pay-Per-Use）に移行。
# 単価はエンドポイントごとに異なり Developer Console にのみ掲載されるため、
# ここではツイート数を記録するにとどめる。


@dataclass
class UsageTracker:
    # Claude API
    input_tokens:  int = 0
    output_tokens: int = 0
    claude_calls:  int = 0

    # X API
    tweets_fetched: int = 0
    x_requests:     int = 0

    def add_claude(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens  += input_tokens
        self.output_tokens += output_tokens
        self.claude_calls  += 1

    def add_x_request(self, tweet_count: int) -> None:
        self.tweets_fetched += tweet_count
        self.x_requests     += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def claude_cost_usd(self) -> float:
        return (
            self.input_tokens  / 1_000_000 * _INPUT_COST_PER_M
            + self.output_tokens / 1_000_000 * _OUTPUT_COST_PER_M
        )

    def to_dict(self) -> dict:
        return {
            "input_tokens":   self.input_tokens,
            "output_tokens":  self.output_tokens,
            "total_tokens":   self.total_tokens,
            "claude_calls":   self.claude_calls,
            "claude_cost":    f"${self.claude_cost_usd:.4f}",
            "tweets_fetched": self.tweets_fetched,
            "x_requests":     self.x_requests,
        }
