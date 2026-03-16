import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    x_bearer_token: str
    anthropic_api_key: str
    claude_model: str = "claude-opus-4-5"
    max_tweets: int = 100
    output_dir: str = "output"
    max_retries: int = 5


def load_config() -> Config:
    token = os.getenv("X_BEARER_TOKEN")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not token:
        raise EnvironmentError("X_BEARER_TOKEN is not set. Copy .env.example to .env and fill in the values.")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill in the values.")
    return Config(
        x_bearer_token=token,
        anthropic_api_key=api_key,
        claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-4-5"),
        max_tweets=int(os.getenv("MAX_TWEETS", "100")),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        max_retries=int(os.getenv("MAX_RETRIES", "5")),
    )
