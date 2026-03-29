"""Blog Crawl DAG — crawls a single source manually.

Crawling only. dlt load and dbt transform are separate DAGs.
"""

from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag, task
from airflow.models.param import Param

from common import DEFAULT_ARGS


@dag(
    dag_id="blog_crawl",
    default_args=DEFAULT_ARGS,
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
        from src.application.crawl_service import crawl_source
        from src.application.source_sync_service import sync_sources
        from src.shared.config import Config

        params = context["params"]
        source_name = params["source_name"]
        partition_date = params.get("partition_date") or context["ds"]

        config = Config()
        sync_sources(config.database.url)

        result = crawl_source(config, source_name, partition_date)
        return result.to_dict()

    crawl()


blog_crawl()
