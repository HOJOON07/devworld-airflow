from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.domain.entities.article import Article
from src.domain.entities.crawl_job import CrawlJob
from src.domain.entities.crawl_source import CrawlSource
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def _build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


class PostgresArticleRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, article: Article) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO articles (
                        id, source_id, url, title, content_text, content_html,
                        author, published_at, discovered_at, raw_storage_key,
                        content_hash, metadata
                    ) VALUES (
                        :id, :source_id, :url, :title, :content_text, :content_html,
                        :author, :published_at, :discovered_at, :raw_storage_key,
                        :content_hash, :metadata
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        content_text = EXCLUDED.content_text,
                        content_html = EXCLUDED.content_html,
                        author = EXCLUDED.author,
                        published_at = EXCLUDED.published_at,
                        raw_storage_key = EXCLUDED.raw_storage_key,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata
                    """
                ),
                {
                    "id": article.id,
                    "source_id": article.source_id,
                    "url": article.url,
                    "title": article.title,
                    "content_text": article.content_text,
                    "content_html": article.content_html,
                    "author": article.author,
                    "published_at": article.published_at,
                    "discovered_at": article.discovered_at,
                    "raw_storage_key": article.raw_storage_key,
                    "content_hash": article.content_hash,
                    "metadata": json.dumps(article.metadata) if article.metadata else None,
                },
            )
            conn.commit()

    def find_by_id(self, article_id: str) -> Article | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM articles WHERE id = :id"),
                {"id": article_id},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_article(row)

    def find_by_url(self, url: str) -> Article | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM articles WHERE url = :url"),
                {"url": url},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_article(row)

    def find_by_source(self, source_id: str) -> list[Article]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM articles WHERE source_id = :source_id"),
                {"source_id": source_id},
            ).mappings().all()
        return [self._row_to_article(row) for row in rows]

    def exists_by_url(self, url: str) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM articles WHERE url = :url LIMIT 1"),
                {"url": url},
            ).first()
        return result is not None

    @staticmethod
    def _row_to_article(row: dict) -> Article:
        return Article(
            id=row["id"],
            source_id=row["source_id"],
            url=row["url"],
            title=row["title"],
            content_text=row["content_text"],
            content_html=row["content_html"],
            author=row["author"],
            published_at=row["published_at"],
            discovered_at=row["discovered_at"],
            raw_storage_key=row["raw_storage_key"],
            content_hash=row["content_hash"],
            metadata=row["metadata"] if row.get("metadata") else None,
        )


class PostgresCrawlSourceRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, source: CrawlSource) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO crawl_sources (
                        id, name, source_type, base_url, feed_url,
                        crawl_config, is_active, created_at
                    ) VALUES (
                        :id, :name, :source_type, :base_url, :feed_url,
                        :crawl_config, :is_active, :created_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        source_type = EXCLUDED.source_type,
                        base_url = EXCLUDED.base_url,
                        feed_url = EXCLUDED.feed_url,
                        crawl_config = EXCLUDED.crawl_config,
                        is_active = EXCLUDED.is_active
                    """
                ),
                {
                    "id": source.id,
                    "name": source.name,
                    "source_type": source.source_type,
                    "base_url": source.base_url,
                    "feed_url": source.feed_url,
                    "crawl_config": json.dumps(source.crawl_config) if source.crawl_config else None,
                    "is_active": source.is_active,
                    "created_at": source.created_at,
                },
            )
            conn.commit()

    def find_by_id(self, source_id: str) -> CrawlSource | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM crawl_sources WHERE id = :id"),
                {"id": source_id},
            ).mappings().first()
        if not row:
            return None
        return CrawlSource(
            id=row["id"],
            name=row["name"],
            source_type=row["source_type"],
            base_url=row["base_url"],
            feed_url=row["feed_url"],
            crawl_config=row["crawl_config"] if row.get("crawl_config") else None,
            is_active=row["is_active"],
            created_at=row["created_at"],
        )

    def find_by_name(self, name: str) -> CrawlSource | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM crawl_sources WHERE name = :name"),
                {"name": name},
            ).mappings().first()
        if not row:
            return None
        return CrawlSource(
            id=row["id"],
            name=row["name"],
            source_type=row["source_type"],
            base_url=row["base_url"],
            feed_url=row["feed_url"],
            crawl_config=row["crawl_config"] if row.get("crawl_config") else None,
            is_active=row["is_active"],
            created_at=row["created_at"],
        )

    def find_all(self) -> list[CrawlSource]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM crawl_sources")
            ).mappings().all()
        return [
            CrawlSource(
                id=row["id"],
                name=row["name"],
                source_type=row["source_type"],
                base_url=row["base_url"],
                feed_url=row["feed_url"],
                crawl_config=row["crawl_config"] if row.get("crawl_config") else None,
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def find_active(self) -> list[CrawlSource]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM crawl_sources WHERE is_active = true")
            ).mappings().all()
        return [
            CrawlSource(
                id=row["id"],
                name=row["name"],
                source_type=row["source_type"],
                base_url=row["base_url"],
                feed_url=row["feed_url"],
                crawl_config=row["crawl_config"] if row.get("crawl_config") else None,
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


class PostgresCrawlJobRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, job: CrawlJob) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO crawl_jobs (
                        id, source_id, partition_date, status,
                        discovered_count, fetched_count, parsed_count,
                        error_message, started_at, completed_at
                    ) VALUES (
                        :id, :source_id, :partition_date, :status,
                        :discovered_count, :fetched_count, :parsed_count,
                        :error_message, :started_at, :completed_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        discovered_count = EXCLUDED.discovered_count,
                        fetched_count = EXCLUDED.fetched_count,
                        parsed_count = EXCLUDED.parsed_count,
                        error_message = EXCLUDED.error_message,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at
                    """
                ),
                {
                    "id": job.id,
                    "source_id": job.source_id,
                    "partition_date": job.partition_date,
                    "status": job.status,
                    "discovered_count": job.discovered_count,
                    "fetched_count": job.fetched_count,
                    "parsed_count": job.parsed_count,
                    "error_message": job.error_message,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                },
            )
            conn.commit()

    def find_by_id(self, job_id: str) -> CrawlJob | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM crawl_jobs WHERE id = :id"),
                {"id": job_id},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_job(row)

    def update_status(self, job_id: str, status: str) -> None:
        now = datetime.utcnow()
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE crawl_jobs
                    SET status = :status, completed_at = :completed_at
                    WHERE id = :id
                    """
                ),
                {"id": job_id, "status": status, "completed_at": now},
            )
            conn.commit()

    def find_by_source_and_date(
        self, source_id: str, partition_date: str
    ) -> CrawlJob | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM crawl_jobs
                    WHERE source_id = :source_id AND partition_date = :partition_date
                    """
                ),
                {"source_id": source_id, "partition_date": partition_date},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_job(row)

    @staticmethod
    def _row_to_job(row: dict) -> CrawlJob:
        return CrawlJob(
            id=row["id"],
            source_id=row["source_id"],
            partition_date=row["partition_date"],
            status=row["status"],
            discovered_count=row["discovered_count"],
            fetched_count=row["fetched_count"],
            parsed_count=row["parsed_count"],
            error_message=row["error_message"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
