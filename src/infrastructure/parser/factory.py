from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.interfaces.parser import Parser


def get_parser(source_type: str) -> Parser:
    """Return a feed/discovery Parser for the given source_type.

    Used in the discover step to parse RSS feeds, sitemaps, etc.
    """
    if source_type == "rss":
        from src.infrastructure.parser.rss_parser import RssParser

        return RssParser()

    raise ValueError(
        f"No parser registered for source_type={source_type!r}. "
        f"Available: ['rss']"
    )


def get_content_parser() -> Parser:
    """Return an HTML content parser for extracting article body.

    Used in the parse step to extract content from raw HTML pages.
    Uses trafilatura for generic extraction across all sources.
    """
    from src.infrastructure.parser.html_parser import HtmlParser

    return HtmlParser()
