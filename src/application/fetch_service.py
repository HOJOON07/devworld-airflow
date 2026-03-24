from __future__ import annotations

from datetime import datetime

from src.domain.entities.article import Article
from src.domain.interfaces.fetcher import Fetcher
from src.domain.interfaces.repository import ArticleRepository
from src.domain.interfaces.storage import StorageAdapter
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class FetchService:
    def __init__(
        self,
        fetcher: Fetcher,
        storage: StorageAdapter,
        article_repo: ArticleRepository,
        raw_bucket: str,
    ) -> None:
        self._fetcher = fetcher
        self._storage = storage
        self._article_repo = article_repo
        self._raw_bucket = raw_bucket

    def fetch_and_store(
        self,
        urls: list[str],
        source_id: str,
        source_name: str,
        partition_date: str,
    ) -> list[Article]:
        """Fetch raw content for each URL and store to R2/MinIO.

        Raw First principle: store raw HTML/JSON before any parsing.
        Returns list of Article entities with raw_storage_key set.
        """
        articles: list[Article] = []

        for url in urls:
            try:
                result = self._fetcher.fetch(url)

                storage_key = self._build_storage_key(
                    source_name, partition_date, url
                )
                self._storage.put_object(
                    self._raw_bucket,
                    storage_key,
                    result.content.encode("utf-8"),
                )

                article = Article(
                    source_id=source_id,
                    url=url,
                    discovered_at=datetime.utcnow(),
                    raw_storage_key=storage_key,
                )
                self._article_repo.save(article)
                articles.append(article)

                logger.info("Fetched and stored url=%s key=%s", url, storage_key)
            except Exception:
                logger.exception("Failed to fetch url=%s", url)

        logger.info(
            "Fetched %d/%d URLs for source=%s", len(articles), len(urls), source_id
        )
        return articles

    @staticmethod
    def _build_storage_key(
        source_name: str, partition_date: str, url: str
    ) -> str:
        """Build a deterministic storage key for raw content.

        Format: raw/{source_name}/{partition_date}/{url_hash}
        """
        from src.shared.hashing import compute_content_hash

        url_hash = compute_content_hash(url)[:16]
        return f"raw/{source_name}/{partition_date}/{url_hash}.html"
