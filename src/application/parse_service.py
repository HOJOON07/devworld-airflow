from __future__ import annotations

from src.domain.entities.article import Article
from src.domain.interfaces.parser import Parser
from src.domain.interfaces.repository import ArticleRepository
from src.domain.interfaces.storage import StorageAdapter
from src.shared.hashing import compute_content_hash
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class ParseService:
    def __init__(
        self,
        parser: Parser,
        storage: StorageAdapter,
        article_repo: ArticleRepository,
        raw_bucket: str,
    ) -> None:
        self._parser = parser
        self._storage = storage
        self._article_repo = article_repo
        self._raw_bucket = raw_bucket

    def parse_articles(
        self,
        articles: list[Article],
        source_type: str,
    ) -> list[Article]:
        """Read raw content from storage, parse, and update articles.

        Reads raw HTML/JSON from R2, parses it, enriches Article entities
        with parsed fields and content hash.
        """
        parsed_articles: list[Article] = []

        for article in articles:
            if not article.raw_storage_key:
                logger.warning("No raw_storage_key for article id=%s", article.id)
                continue

            try:
                raw_bytes = self._storage.get_object(
                    self._raw_bucket, article.raw_storage_key
                )
                raw_content = raw_bytes.decode("utf-8")

                parsed_list = self._parser.parse(raw_content, source_type)
                if not parsed_list:
                    logger.warning("No parsed result for article id=%s", article.id)
                    continue

                parsed = parsed_list[0]
                article.title = parsed.title
                article.content_text = parsed.content_text
                article.content_html = parsed.content_html
                article.author = parsed.author
                article.published_at = parsed.published_at
                article.metadata = parsed.metadata

                if article.content_text:
                    article.content_hash = compute_content_hash(article.content_text)

                self._article_repo.save(article)
                parsed_articles.append(article)

                logger.info("Parsed article id=%s url=%s", article.id, article.url)
            except Exception:
                logger.exception("Failed to parse article id=%s", article.id)

        logger.info(
            "Parsed %d/%d articles", len(parsed_articles), len(articles)
        )
        return parsed_articles
