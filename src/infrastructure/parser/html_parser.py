from __future__ import annotations

from datetime import datetime

import trafilatura

from src.domain.interfaces.parser import ParsedArticle
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class HtmlParser:
    """Generic HTML content parser using trafilatura.

    Extracts article body, title, author, date from any HTML page.
    Works across most tech blogs without source-specific rules.
    """

    def parse(self, raw_content: str, source_type: str) -> list[ParsedArticle]:
        result = trafilatura.extract(
            raw_content,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            with_metadata=True,
        )

        metadata = trafilatura.extract(
            raw_content,
            include_comments=False,
            output_format="xmltei",
            with_metadata=True,
        )

        title = None
        author = None
        published_at = None
        content_html = None

        meta = trafilatura.metadata.extract_metadata(raw_content)
        if meta:
            title = meta.title
            author = meta.author
            if meta.date:
                published_at = self._parse_date(meta.date)

        content_html_result = trafilatura.extract(
            raw_content,
            include_comments=False,
            include_tables=True,
            output_format="html",
        )

        if not result:
            logger.warning("trafilatura could not extract content")
            return []

        article = ParsedArticle(
            url="",
            title=title,
            content_text=result,
            content_html=content_html_result,
            author=author,
            published_at=published_at,
            metadata={},
        )

        logger.info("Extracted article: title=%s, text_len=%d", title, len(result))
        return [article]

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
