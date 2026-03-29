from __future__ import annotations

import os
from datetime import datetime, timezone

import dlt
from sqlalchemy import create_engine, text

from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def _configure_s3_env(config: Config) -> None:
    """Set S3 environment variables for DuckLake/DuckDB data file access."""
    storage = config.storage
    os.environ.setdefault("AWS_ACCESS_KEY_ID", storage.access_key)
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", storage.secret_key)
    os.environ.setdefault("AWS_ENDPOINT_URL", storage.endpoint_url)
    os.environ.setdefault("AWS_REGION", storage.region)
    os.environ.setdefault("AWS_ALLOW_HTTP", "true")


def _fetch_articles_by_source(
    database_url: str, source_name: str, partition_date: str
) -> list[dict]:
    """Query articles for a specific source and partition date."""
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    a.id::text AS id,
                    a.source_id::text AS source_id,
                    cs.name AS source_name,
                    a.url,
                    a.title,
                    a.content_text,
                    a.content_html,
                    a.author,
                    a.published_at,
                    a.discovered_at,
                    a.raw_storage_key,
                    a.content_hash,
                    a.metadata::text AS metadata
                FROM articles a
                JOIN crawl_sources cs ON a.source_id = cs.id
                WHERE cs.name = :source_name
                  AND CAST(a.discovered_at AS date) = CAST(:partition_date AS date)
                """
            ),
            {"source_name": source_name, "partition_date": partition_date},
        ).mappings().all()

    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            **dict(row),
            "partition_date": partition_date,
            "crawled_at": now,
        }
        for row in rows
    ]


def load_articles_to_bronze(
    config: Config, source_name: str, partition_date: str
) -> int:
    """Load articles from PostgreSQL to DuckLake Bronze as parquet.

    Args:
        config: Application config.
        source_name: Crawl source name to filter by.
        partition_date: Date string (YYYY-MM-DD) to partition by.

    Returns:
        Number of articles loaded.
    """
    storage = config.storage
    db = config.database
    ducklake = config.ducklake

    records = _fetch_articles_by_source(db.url, source_name, partition_date)
    if not records:
        logger.info("No articles to load for source=%s partition_date=%s", source_name, partition_date)
        return 0

    _configure_s3_env(config)

    from dlt.common.storages.configuration import FilesystemConfiguration
    from dlt.destinations.impl.ducklake.configuration import DuckLakeCredentials

    storage_config = FilesystemConfiguration(
        bucket_url=ducklake.data_path,
        credentials={
            "aws_access_key_id": storage.access_key,
            "aws_secret_access_key": storage.secret_key,
            "endpoint_url": storage.endpoint_url,
            "region_name": storage.region,
        },
    )

    credentials = DuckLakeCredentials(
        ducklake_name="devworld_lake",
        catalog=ducklake.catalog_connection_url,
        storage=storage_config,
    )

    pipeline = dlt.pipeline(
        pipeline_name=f"bronze_{source_name}",
        destination=dlt.destinations.ducklake(credentials=credentials),
        dataset_name="bronze",
    )

    @dlt.resource(
        name="articles",
        write_disposition="append",
        columns={
            "metadata": {"data_type": "text"},
            "published_at": {"data_type": "text"},
        },
    )
    def _resource():
        yield records

    load_info = pipeline.run(_resource())

    logger.info("Bronze load complete for source=%s: %s", source_name, load_info)
    return len(records)
