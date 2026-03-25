"""dlt Load DAG — loads articles from PostgreSQL to Bronze parquet.

Runs daily at KST 01:00 (UTC 16:00), after blog_crawl_all.
Loads all active sources' articles to MinIO Bronze bucket as parquet.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="dlt_load",
    schedule="0 16 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dlt", "bronze", "load"],
    params={
        "source_name": Param(
            default="",
            description="Specific source to load. Empty = all active sources.",
        ),
    },
)
def dlt_load():
    @task()
    def get_sources(**context) -> list[str]:
        """Get sources to load. If source_name param given, use that. Otherwise all active."""
        from src.infrastructure.repository.postgres_repository import (
            PostgresCrawlSourceRepository,
        )
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("dlt_load.get_sources")
        config = Config()

        params = context["params"]
        source_name = params.get("source_name", "")

        if source_name:
            logger.info("Loading specific source: %s", source_name)
            return [source_name]

        source_repo = PostgresCrawlSourceRepository(config.database.url)
        sources = source_repo.find_active()
        names = [s.name for s in sources]
        logger.info("Loading all active sources: %s", names)
        return names

    @task()
    def load_source(source_name: str, **context) -> dict:
        """Load articles for a single source to Bronze parquet."""
        from src.application.load_service import load_articles_to_bronze
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging(f"dlt_load.{source_name}")
        partition_date = context["ds"]
        config = Config()

        try:
            logger.info("[load] source=%s partition_date=%s", source_name, partition_date)
            count = load_articles_to_bronze(config, source_name, partition_date)
            logger.info("[done] %d articles loaded for source=%s", count, source_name)
            return {"source": source_name, "loaded": count}
        except Exception as e:
            logger.exception("[failed] source=%s", source_name)
            return {"source": source_name, "loaded": 0, "error": str(e)[:200]}

    @task()
    def summarize(results: list[dict]) -> None:
        """Log summary of dlt load results."""
        from src.shared.logging import setup_logging

        logger = setup_logging("dlt_load.summary")
        total = sum(r["loaded"] for r in results)
        logger.info("dlt load complete: %d sources, %d total articles", len(results), total)
        for r in results:
            logger.info("  %s: loaded=%d", r["source"], r["loaded"])

    sources = get_sources()
    results = load_source.expand(source_name=sources)
    summarize(results)


dlt_load()
