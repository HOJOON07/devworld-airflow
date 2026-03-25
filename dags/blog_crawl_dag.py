"""Blog Crawl DAG — crawls a single source manually.

Crawling only. dlt load and dbt transform are separate DAGs.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="blog_crawl",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crawl", "blog"],
    params={
        "source_name": Param(
            default="",
            type="string",
            description="CrawlSource name (e.g. toss-tech, daangn-tech)",
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
    def crawl(**context) -> dict:
        """Run crawl for a single source."""
        from src.application.discovery_service import DiscoveryService
        from src.application.fetch_service import FetchService
        from src.application.parse_service import ParseService
        from src.infrastructure.fetcher.http_fetcher import HttpFetcher
        from src.infrastructure.parser.factory import get_content_parser, get_parser
        from src.infrastructure.repository.postgres_repository import (
            PostgresArticleRepository,
            PostgresCrawlSourceRepository,
        )
        from src.infrastructure.storage.s3_storage import S3Storage
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        params = context["params"]
        source_name = params["source_name"]
        partition_date = params.get("partition_date") or context["ds"]

        logger = setup_logging(f"blog_crawl.{source_name}")

        config = Config()

        from src.application.source_sync_service import sync_sources
        sync_sources(config.database.url)

        source_repo = PostgresCrawlSourceRepository(config.database.url)
        article_repo = PostgresArticleRepository(config.database.url)
        storage = S3Storage(config.storage)
        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        # 1. Discover
        logger.info("[discover] source=%s", source_name)
        discovery = DiscoveryService(
            fetcher=HttpFetcher(),
            parser=get_parser(source.source_type),
            article_repo=article_repo,
            storage=storage,
            raw_bucket=config.storage.raw_bucket,
        )
        disc_result = discovery.discover(source, partition_date)

        if disc_result.total_new == 0:
            logger.info("No new articles for source=%s", source_name)
            return {"source": source_name, "discovered": 0, "fetched": 0, "parsed": 0}

        all_articles = list(disc_result.saved_articles)

        # 2. Fetch
        if disc_result.urls_to_fetch:
            logger.info("[fetch] %d URLs for source=%s", len(disc_result.urls_to_fetch), source_name)
            fetch_service = FetchService(
                fetcher=HttpFetcher(),
                storage=storage,
                article_repo=article_repo,
                raw_bucket=config.storage.raw_bucket,
            )
            fetched = fetch_service.fetch_and_store(
                disc_result.urls_to_fetch, source.id, source.name, partition_date
            )
            all_articles.extend(fetched)

        # 3. Parse
        articles_to_parse = [a for a in all_articles if a not in disc_result.saved_articles]
        parsed_count = len(disc_result.saved_articles)

        if articles_to_parse:
            logger.info("[parse] %d articles for source=%s", len(articles_to_parse), source_name)
            parse_service = ParseService(
                parser=get_content_parser(),
                storage=storage,
                article_repo=article_repo,
                raw_bucket=config.storage.raw_bucket,
            )
            parsed = parse_service.parse_articles(articles_to_parse, source.source_type)
            parsed_count += len(parsed)

        result = {
            "source": source_name,
            "discovered": disc_result.total_new,
            "fetched": len(all_articles),
            "parsed": parsed_count,
        }
        logger.info("[done] %s", result)
        return result

    crawl()


blog_crawl()
