from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tweet:
    id: str
    text: str
    author_id: str
    created_at: datetime
    url: str
