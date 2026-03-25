from __future__ import annotations

from datetime import datetime

import trafilatura

from src.domain.interfaces.parser import ParsedArticle
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class HtmlParser:
    """Generic HTML content parser using trafilatura.

    Used for sources without content:encoded (e.g. line-tech, banksalad-tech).
    Extracts article body, title, author, date from raw HTML pages.
    """

    def parse(self, raw_content: str, source_type: str) -> list[ParsedArticle]:
        meta = trafilatura.metadata.extract_metadata(raw_content)

        content_text = trafilatura.extract(
            raw_content,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )

        if not content_text:
            logger.warning("trafilatura could not extract content")
            return []

        content_html = trafilatura.extract(
            raw_content,
            include_comments=False,
            include_tables=True,
            output_format="html",
        )

        title = meta.title if meta else None
        author = meta.author if meta else None
        published_at = self._parse_date(meta.date) if meta and meta.date else None

        article = ParsedArticle(
            url="",
            title=title,
            content_text=content_text,
            content_html=content_html,
            author=author,
            published_at=published_at,
            metadata={},
        )

        logger.info("Extracted: title=%s, text_len=%d", title, len(content_text))
        return [article]

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
