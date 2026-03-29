"""dlt Load DAG — loads articles from PostgreSQL to DuckLake Bronze.

Triggered by articles_ready asset (after blog_crawl_all).
Produces bronze_ready asset to trigger dbt_silver.

Note: dlt ducklake destination uses PostgreSQL catalog with CREATE SCHEMA,
which has race conditions under parallel execution. Articles are loaded
sequentially in a single task to avoid this.
"""

from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag, task
from airflow.models.param import Param

from assets import articles_ready, bronze_ready
from common import DEFAULT_ARGS


@dag(
    dag_id="dlt_load",
    default_args=DEFAULT_ARGS,
    schedule=articles_ready,
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
    @task(outlets=[bronze_ready])
    def load_all_sources(**context) -> dict:
        """Load all active sources to DuckLake Bronze sequentially."""
        from datetime import datetime as dt, timezone

        from src.application.load_service import load_articles_to_bronze
        from src.infrastructure.repository.postgres_repository import (
            PostgresCrawlSourceRepository,
        )
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("dlt_load")
        config = Config()

        params = context["params"]
        source_name = params.get("source_name", "")
        partition_date = context.get("ds") or dt.now(timezone.utc).strftime("%Y-%m-%d")

        # Get sources to load
        if source_name:
            source_names = [source_name]
        else:
            source_repo = PostgresCrawlSourceRepository(config.database.url)
            sources = source_repo.find_active()
            source_names = [s.name for s in sources]

        logger.info("Loading %d sources for partition_date=%s", len(source_names), partition_date)

        results = []
        total_loaded = 0

        for name in source_names:
            try:
                count = load_articles_to_bronze(config, name, partition_date)
                results.append({"source": name, "loaded": count})
                total_loaded += count
                if count > 0:
                    logger.info("[done] %d articles loaded for source=%s", count, name)
            except Exception as e:
                logger.exception("[failed] source=%s", name)
                results.append({"source": name, "loaded": 0, "error": str(e)[:200]})

        logger.info(
            "dlt load complete: %d sources, %d total articles",
            len(results), total_loaded,
        )
        return {"sources": len(results), "total_loaded": total_loaded}

    load_all_sources()


dlt_load()
