from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.entities.article import Article
from src.domain.entities.crawl_source import CrawlSource
from src.domain.interfaces.fetcher import Fetcher
from src.domain.interfaces.parser import Parser
from src.domain.interfaces.repository import ArticleRepository
from src.domain.interfaces.storage import StorageAdapter
from src.shared.hashing import compute_content_hash
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class DiscoveryResult:
    """RSS content:encoded 유무에 따라 두 종류의 결과를 반환."""

    urls_to_fetch: list[str] = field(default_factory=list)
    saved_articles: list[Article] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return len(self.urls_to_fetch) + len(self.saved_articles)


class DiscoveryService:
    def __init__(
        self,
        fetcher: Fetcher,
        parser: Parser,
        article_repo: ArticleRepository,
        storage: StorageAdapter | None = None,
        raw_bucket: str = "",
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._article_repo = article_repo
        self._storage = storage
        self._raw_bucket = raw_bucket

    def discover(
        self,
        source: CrawlSource,
        partition_date: str = "",
    ) -> DiscoveryResult:
        feed_url = source.feed_url or source.base_url
        logger.info("Discovering for source=%s url=%s", source.name, feed_url)

        result = self._fetcher.fetch(feed_url)
        parsed = self._parser.parse(result.content, source.source_type)

        urls_to_fetch: list[str] = []
        saved_articles: list[Article] = []

        url_filter = (source.crawl_config or {}).get("url_filter")

        for item in parsed:
            if not item.url:
                continue
            if url_filter and url_filter not in item.url:
                continue
            if self._article_repo.exists_by_url(item.url):
                continue

            if item.content_html and self._storage and self._raw_bucket:
                article = self._save_rss_content(source, item, partition_date)
                if article:
                    saved_articles.append(article)
            else:
                urls_to_fetch.append(item.url)

        logger.info(
            "source=%s: %d from RSS content, %d need fetch",
            source.name,
            len(saved_articles),
            len(urls_to_fetch),
        )
        return DiscoveryResult(
            urls_to_fetch=urls_to_fetch,
            saved_articles=saved_articles,
        )

    def _save_rss_content(
        self,
        source: CrawlSource,
        item,
        partition_date: str,
    ) -> Article | None:
        try:
            url_hash = compute_content_hash(item.url)[:16]
            storage_key = f"raw/{source.name}/{partition_date}/{url_hash}.html"

            self._storage.put_object(
                self._raw_bucket,
                storage_key,
                item.content_html.encode("utf-8"),
            )

            article = Article(
                source_id=source.id,
                url=item.url,
                title=item.title,
                content_text=item.content_text,
                content_html=item.content_html,
                author=item.author,
                published_at=item.published_at,
                discovered_at=datetime.utcnow(),
                raw_storage_key=storage_key,
                metadata=item.metadata,
            )

            if article.content_text:
                article.content_hash = compute_content_hash(article.content_text)

            self._article_repo.save(article)
            logger.info("Saved RSS content: url=%s key=%s", item.url, storage_key)
            return article
        except Exception:
            logger.exception("Failed to save RSS content: url=%s", item.url)
            return None
