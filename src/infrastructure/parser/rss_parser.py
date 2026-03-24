from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser

from src.domain.interfaces.parser import ParsedArticle
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class RssParser:
    def parse(self, raw_content: str, source_type: str) -> list[ParsedArticle]:
        if source_type != "rss":
            logger.warning("RssParser called with source_type=%s, skipping", source_type)
            return []

        feed = feedparser.parse(raw_content)
        articles: list[ParsedArticle] = []

        for entry in feed.entries:
            published_at = self._parse_date(entry.get("published"))
            content_html = self._extract_content(entry)

            articles.append(
                ParsedArticle(
                    url=entry.get("link", ""),
                    title=entry.get("title"),
                    content_text=entry.get("summary"),
                    content_html=content_html,
                    author=entry.get("author"),
                    published_at=published_at,
                    metadata={
                        "tags": [t.get("term") for t in entry.get("tags", [])],
                    },
                )
            )

        logger.info("Parsed %d articles from RSS feed", len(articles))
        return articles

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_content(entry: dict) -> str | None:
        content_list = entry.get("content", [])
        if content_list:
            return content_list[0].get("value")
        return None
