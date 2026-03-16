from dataclasses import dataclass, field

from fetcher.models import Tweet


@dataclass
class Topic:
    name: str
    description: str


@dataclass
class TweetGroup:
    topic: Topic
    tweets: list[Tweet] = field(default_factory=list)
