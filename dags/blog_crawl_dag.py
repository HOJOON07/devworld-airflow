"""Blog Crawl DAG — orchestrates tech blog crawling pipeline.

Thin DAG: all business logic lives in src/ modules.
Parameterized by source_name and partition_date for backfill support.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="blog_crawl",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crawl", "blog"],
    params={
        "source_name": Param(
            default="",
            type="string",
            description="CrawlSource name (e.g. kakao-tech, naver-d2)",
        ),
        "partition_date": Param(
            default="",
            type="string",
            description="Partition date (YYYY-MM-DD). Defaults to ds if empty.",
        ),
    },
)
def blog_crawl():
    @task()
    def discover(**context) -> list[str]:
        """Discover new article URLs from the source feed."""
        from src.application.discovery_service import DiscoveryService
        from src.infrastructure.fetcher.http_fetcher import HttpFetcher
        from src.infrastructure.parser.factory import get_parser
        from src.infrastructure.repository.postgres_repository import (
            PostgresArticleRepository,
            PostgresCrawlSourceRepository,
        )
        from src.shared.config import Config

        params = context["params"]
        source_name = params["source_name"]

        config = Config()
        source_repo = PostgresCrawlSourceRepository(config.database.url)
        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        service = DiscoveryService(
            fetcher=HttpFetcher(),
            parser=get_parser(source.source_type),
            article_repo=PostgresArticleRepository(config.database.url),
        )
        return service.discover(source)

    @task()
    def fetch(urls: list[str], **context) -> list[dict]:
        """Fetch raw content and store to R2/MinIO."""
        from src.application.fetch_service import FetchService
        from src.infrastructure.fetcher.http_fetcher import HttpFetcher
        from src.infrastructure.repository.postgres_repository import (
            PostgresArticleRepository,
            PostgresCrawlSourceRepository,
        )
        from src.infrastructure.storage.s3_storage import S3Storage
        from src.shared.config import Config

        params = context["params"]
        source_name = params["source_name"]
        partition_date = params.get("partition_date") or context["ds"]

        config = Config()
        source_repo = PostgresCrawlSourceRepository(config.database.url)
        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        service = FetchService(
            fetcher=HttpFetcher(),
            storage=S3Storage(config.storage),
            article_repo=PostgresArticleRepository(config.database.url),
            raw_bucket=config.storage.raw_bucket,
        )
        articles = service.fetch_and_store(urls, source.id, source.name, partition_date)
        return [
            {"id": a.id, "raw_storage_key": a.raw_storage_key}
            for a in articles
        ]

    @task()
    def parse(article_refs: list[dict], **context) -> int:
        """Parse raw content into structured articles."""
        from src.application.parse_service import ParseService
        from src.infrastructure.parser.factory import get_content_parser
        from src.infrastructure.repository.postgres_repository import (
            PostgresArticleRepository,
            PostgresCrawlSourceRepository,
        )
        from src.infrastructure.storage.s3_storage import S3Storage
        from src.shared.config import Config

        params = context["params"]
        source_name = params["source_name"]

        config = Config()
        article_repo = PostgresArticleRepository(config.database.url)
        source_repo = PostgresCrawlSourceRepository(config.database.url)

        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        articles = []
        for ref in article_refs:
            article = article_repo.find_by_id(ref["id"])
            if article:
                articles.append(article)

        service = ParseService(
            parser=get_content_parser(),
            storage=S3Storage(config.storage),
            article_repo=article_repo,
            raw_bucket=config.storage.raw_bucket,
        )
        parsed = service.parse_articles(articles, source.source_type)
        return len(parsed)

    @task()
    def load(parsed_count: int, **context) -> None:
        """Load parsed articles via dlt (placeholder)."""
        from src.shared.logging import setup_logging

        params = context["params"]
        source_name = params["source_name"]
        partition_date = params.get("partition_date") or context["ds"]

        logger = setup_logging("blog_crawl.load")
        logger.info(
            "Load step: %d articles for source=%s date=%s (dlt integration pending)",
            parsed_count,
            source_name,
            partition_date,
        )

    # Task flow
    discovered_urls = discover()
    fetched_refs = fetch(urls=discovered_urls)
    parsed_count = parse(article_refs=fetched_refs)
    load(parsed_count=parsed_count)


blog_crawl()
