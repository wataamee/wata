import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert topic name to a filesystem-safe slug."""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Replace spaces and special characters with hyphens
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.lower() or "article"


def save_article(topic_name: str, markdown_content: str, output_dir: str = "output") -> Path:
    """Save a Markdown article to output_dir/<slug>.md and return the path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    slug = _slugify(topic_name)
    path = out / f"{slug}.md"
    path.write_text(markdown_content, encoding="utf-8")
    logger.info("Saved article: %s", path)
    return path
