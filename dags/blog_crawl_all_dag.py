"""Blog Crawl All DAG — automatically crawls every active source.

No params needed. Runs daily at KST 00:00 (UTC 15:00).
Each active source is crawled in parallel using dynamic task mapping.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="blog_crawl_all",
    schedule="0 15 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crawl", "blog", "all"],
)
def blog_crawl_all():
    @task()
    def sync_sources() -> dict:
        """Sync config/sources.yml to crawl_sources DB table."""
        from src.application.source_sync_service import sync_sources
        from src.shared.config import Config

        config = Config()
        return sync_sources(config.database.url)

    @task()
    def get_active_sources() -> list[str]:
        """Get all active source names from DB."""
        from src.infrastructure.repository.postgres_repository import (
            PostgresCrawlSourceRepository,
        )
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("blog_crawl_all.get_sources")
        config = Config()
        source_repo = PostgresCrawlSourceRepository(config.database.url)
        sources = source_repo.find_active()
        names = [s.name for s in sources]
        logger.info("Found %d active sources: %s", len(names), names)
        return names

    @task()
    def crawl_source(source_name: str, **context) -> dict:
        """Run full crawl pipeline for a single source with job tracking."""
        from src.application.discovery_service import DiscoveryService
        from src.application.fetch_service import FetchService
        from src.application.parse_service import ParseService
        from src.domain.entities.crawl_job import CrawlJob
        from src.infrastructure.fetcher.http_fetcher import HttpFetcher
        from src.infrastructure.parser.factory import get_content_parser, get_parser
        from src.infrastructure.repository.postgres_repository import (
            PostgresArticleRepository,
            PostgresCrawlJobRepository,
            PostgresCrawlSourceRepository,
        )
        from src.infrastructure.storage.s3_storage import S3Storage
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging(f"blog_crawl_all.{source_name}")
        partition_date = context["ds"]

        config = Config()
        source_repo = PostgresCrawlSourceRepository(config.database.url)
        article_repo = PostgresArticleRepository(config.database.url)
        job_repo = PostgresCrawlJobRepository(config.database.url)
        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        # Create crawl job record
        job = CrawlJob(
            source_id=source.id,
            partition_date=partition_date,
            status="running",
            started_at=datetime.utcnow(),
        )
        job_repo.save(job)

        try:
            storage = S3Storage(config.storage)

            # 1. Discover (RSS content:encoded 있으면 바로 저장됨)
            logger.info("[discover] source=%s", source_name)
            discovery = DiscoveryService(
                fetcher=HttpFetcher(),
                parser=get_parser(source.source_type),
                article_repo=article_repo,
                storage=storage,
                raw_bucket=config.storage.raw_bucket,
            )
            disc_result = discovery.discover(source, partition_date)
            job.discovered_count = disc_result.total_new

            if disc_result.total_new == 0:
                logger.info("No new articles for source=%s", source_name)
                job.status = "success"
                job.completed_at = datetime.utcnow()
                job_repo.save(job)
                return {"source": source_name, "discovered": 0, "fetched": 0, "parsed": 0}

            all_articles = list(disc_result.saved_articles)

            # 2. Fetch (content:encoded 없는 URL만 HTTP fetch)
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
            job.fetched_count = len(all_articles)

            # 3. Parse (fetch한 것만 — RSS content는 이미 파싱됨)
            articles_to_parse = [a for a in all_articles if a not in disc_result.saved_articles]
            parsed_count = len(disc_result.saved_articles)  # RSS content는 이미 파싱됨

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
            job.parsed_count = parsed_count

            # Success
            job.status = "success"
            job.completed_at = datetime.utcnow()
            job_repo.save(job)

            result = {
                "source": source_name,
                "discovered": disc_result.total_new,
                "fetched": len(all_articles),
                "parsed": parsed_count,
            }
            logger.info("[done] %s", result)
            return result

        except Exception as e:
            # Record failure
            job.status = "failed"
            job.error_message = str(e)[:500]
            job.completed_at = datetime.utcnow()
            job_repo.save(job)
            logger.exception("[failed] source=%s", source_name)
            return {"source": source_name, "discovered": 0, "fetched": 0, "parsed": 0, "error": str(e)[:200]}

    @task()
    def summarize(results: list[dict]) -> None:
        """Log summary of all crawl results."""
        from src.shared.logging import setup_logging

        logger = setup_logging("blog_crawl_all.summary")
        total_d = sum(r["discovered"] for r in results)
        total_f = sum(r["fetched"] for r in results)
        total_p = sum(r["parsed"] for r in results)
        logger.info(
            "Crawl complete: %d sources, %d discovered, %d fetched, %d parsed",
            len(results),
            total_d,
            total_f,
            total_p,
        )
        for r in results:
            logger.info(
                "  %s: discovered=%d fetched=%d parsed=%d",
                r["source"],
                r["discovered"],
                r["fetched"],
                r["parsed"],
            )

    # Flow: sync → get sources → crawl each (parallel) → summarize
    sync_result = sync_sources()
    sources = get_active_sources()
    sync_result >> sources  # sync 완료 후 소스 조회
    results = crawl_source.expand(source_name=sources)
    summarize(results)


blog_crawl_all()
