"""Blog Crawl All DAG — automatically crawls every active source.

Crawling only. dlt load and dbt transform are separate DAGs.
Runs daily at KST 00:00 (UTC 15:00).
"""

from __future__ import annotations

from datetime import datetime, timezone

from airflow.sdk import dag, task

from assets import articles_ready
from common import DEFAULT_ARGS


@dag(
    dag_id="blog_crawl_all",
    default_args=DEFAULT_ARGS,
    schedule="0 15 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crawl", "blog"],
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
    def crawl_source_with_tracking(source_name: str, **context) -> dict:
        """Run crawl pipeline for a single source with CrawlJob tracking."""
        from src.application.crawl_service import crawl_source
        from src.domain.entities.crawl_job import CrawlJob
        from src.infrastructure.repository.postgres_repository import (
            PostgresCrawlJobRepository,
        )
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging(f"blog_crawl_all.{source_name}")
        partition_date = context["ds"]
        config = Config()
        job_repo = PostgresCrawlJobRepository(config.database.url)

        source_repo_mod = __import__(
            "src.infrastructure.repository.postgres_repository", fromlist=["PostgresCrawlSourceRepository"]
        )
        source_repo = source_repo_mod.PostgresCrawlSourceRepository(config.database.url)
        source = source_repo.find_by_name(source_name)
        if not source:
            raise ValueError(f"Source not found: {source_name}")

        job = CrawlJob(
            source_id=source.id,
            partition_date=partition_date,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        job_repo.save(job)

        try:
            result = crawl_source(config, source_name, partition_date)

            job.discovered_count = result.discovered
            job.fetched_count = result.fetched
            job.parsed_count = result.parsed
            job.status = "success"
            job.completed_at = datetime.now(timezone.utc)
            job_repo.save(job)

            return result.to_dict()

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)[:500]
            job.completed_at = datetime.now(timezone.utc)
            job_repo.save(job)
            logger.exception("[failed] source=%s", source_name)
            return {"source": source_name, "discovered": 0, "fetched": 0, "parsed": 0, "error": str(e)[:200]}

    @task(outlets=[articles_ready])
    def summarize(results: list[dict]) -> None:
        """Log summary of all crawl results."""
        from src.shared.logging import setup_logging

        logger = setup_logging("blog_crawl_all.summary")
        total_d = sum(r["discovered"] for r in results)
        total_f = sum(r["fetched"] for r in results)
        total_p = sum(r["parsed"] for r in results)
        logger.info(
            "Crawl complete: %d sources, %d discovered, %d fetched, %d parsed",
            len(results), total_d, total_f, total_p,
        )
        for r in results:
            logger.info(
                "  %s: discovered=%d fetched=%d parsed=%d",
                r["source"], r["discovered"], r["fetched"], r["parsed"],
            )

    sync_result = sync_sources()
    sources = get_active_sources()
    sync_result >> sources
    results = crawl_source_with_tracking.expand(source_name=sources)
    summarize(results)


blog_crawl_all()
