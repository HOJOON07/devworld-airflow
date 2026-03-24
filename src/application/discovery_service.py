from __future__ import annotations

from src.domain.entities.crawl_source import CrawlSource
from src.domain.interfaces.fetcher import Fetcher
from src.domain.interfaces.parser import Parser
from src.domain.interfaces.repository import ArticleRepository
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class DiscoveryService:
    def __init__(
        self,
        fetcher: Fetcher,
        parser: Parser,
        article_repo: ArticleRepository,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._article_repo = article_repo

    def discover(self, source: CrawlSource) -> list[str]:
        """Discover new article URLs from a crawl source.

        Fetches the feed/sitemap, parses it to extract URLs,
        and filters out already-known URLs.

        Returns list of new (not yet crawled) URLs.
        """
        feed_url = source.feed_url or source.base_url
        logger.info(
            "Discovering articles for source=%s url=%s", source.name, feed_url
        )

        result = self._fetcher.fetch(feed_url)
        parsed = self._parser.parse(result.content, source.source_type)

        all_urls = [article.url for article in parsed if article.url]
        new_urls = [
            url for url in all_urls if not self._article_repo.exists_by_url(url)
        ]

        logger.info(
            "Discovered %d total, %d new URLs for source=%s",
            len(all_urls),
            len(new_urls),
            source.name,
        )
        return new_urls
