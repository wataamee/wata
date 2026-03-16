from dataclasses import dataclass, field

# Claude pricing (per 1M tokens) — claude-opus-4-5
_INPUT_COST_PER_M  = 15.0   # USD
_OUTPUT_COST_PER_M = 75.0   # USD

# X API v2 read pricing (cost per tweet read)
# Basic:  $100 /month  for    10,000 tweet reads → $0.01000 / tweet
# Pro:  $5,000 /month  for 1,000,000 tweet reads → $0.00500 / tweet
_X_BASIC_PER_TWEET = 100 / 10_000      # $0.01
_X_PRO_PER_TWEET   = 5_000 / 1_000_000 # $0.005


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

    @property
    def x_cost_basic_usd(self) -> float:
        return self.tweets_fetched * _X_BASIC_PER_TWEET

    @property
    def x_cost_pro_usd(self) -> float:
        return self.tweets_fetched * _X_PRO_PER_TWEET

    def to_dict(self) -> dict:
        return {
            "input_tokens":      self.input_tokens,
            "output_tokens":     self.output_tokens,
            "total_tokens":      self.total_tokens,
            "claude_calls":      self.claude_calls,
            "claude_cost":       f"${self.claude_cost_usd:.4f}",
            "tweets_fetched":    self.tweets_fetched,
            "x_requests":        self.x_requests,
            "x_cost_basic":      f"${self.x_cost_basic_usd:.4f}",
            "x_cost_pro":        f"${self.x_cost_pro_usd:.4f}",
        }
