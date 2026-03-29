"""Crawl Service — common discover → fetch → parse pipeline for blog sources."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass
class CrawlResult:
    source: str
    discovered: int
    fetched: int
    parsed: int
    error: str | None = None

    def to_dict(self) -> dict:
        d = {"source": self.source, "discovered": self.discovered, "fetched": self.fetched, "parsed": self.parsed}
        if self.error:
            d["error"] = self.error
        return d


def crawl_source(config: Config, source_name: str, partition_date: str) -> CrawlResult:
    """Run discover → fetch → parse pipeline for a single source.

    Args:
        config: Application config.
        source_name: CrawlSource name.
        partition_date: Date string (YYYY-MM-DD).

    Returns:
        CrawlResult with counts.
    """
    log = setup_logging(f"crawl.{source_name}")

    source_repo = PostgresCrawlSourceRepository(config.database.url)
    article_repo = PostgresArticleRepository(config.database.url)
    storage = S3Storage(config.storage)

    source = source_repo.find_by_name(source_name)
    if not source:
        raise ValueError(f"Source not found: {source_name}")

    # 1. Discover
    log.info("[discover] source=%s", source_name)
    discovery = DiscoveryService(
        fetcher=HttpFetcher(),
        parser=get_parser(source.source_type),
        article_repo=article_repo,
        storage=storage,
        raw_bucket=config.storage.raw_bucket,
    )
    disc_result = discovery.discover(source, partition_date)

    if disc_result.total_new == 0:
        log.info("No new articles for source=%s", source_name)
        return CrawlResult(source=source_name, discovered=0, fetched=0, parsed=0)

    all_articles = list(disc_result.saved_articles)

    # 2. Fetch
    if disc_result.urls_to_fetch:
        log.info("[fetch] %d URLs for source=%s", len(disc_result.urls_to_fetch), source_name)
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
        log.info("[parse] %d articles for source=%s", len(articles_to_parse), source_name)
        parse_service = ParseService(
            parser=get_content_parser(),
            storage=storage,
            article_repo=article_repo,
            raw_bucket=config.storage.raw_bucket,
        )
        parsed = parse_service.parse_articles(articles_to_parse, source.source_type)
        parsed_count += len(parsed)

    result = CrawlResult(
        source=source_name,
        discovered=disc_result.total_new,
        fetched=len(all_articles),
        parsed=parsed_count,
    )
    log.info("[done] %s", result.to_dict())
    return result
