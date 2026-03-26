from __future__ import annotations

from datetime import datetime

import dlt
from sqlalchemy import create_engine, text

from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


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
                """
            ),
            {"source_name": source_name},
        ).mappings().all()

    now = datetime.utcnow().isoformat()
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
    """Load articles from PostgreSQL to MinIO bronze bucket as parquet.

    Args:
        config: Application config.
        source_name: Crawl source name to filter by.
        partition_date: Date string (YYYY-MM-DD) to partition by.

    Returns:
        Number of articles loaded.
    """
    storage = config.storage
    db = config.database

    records = _fetch_articles_by_source(db.url, source_name, partition_date)
    if not records:
        logger.info("No articles to load for source=%s partition_date=%s", source_name, partition_date)
        return 0

    pipeline = dlt.pipeline(
        pipeline_name=f"bronze_{source_name}",
        destination=dlt.destinations.filesystem(
            bucket_url=f"s3://{storage.bronze_bucket}",
            credentials={
                "aws_access_key_id": storage.access_key,
                "aws_secret_access_key": storage.secret_key,
                "endpoint_url": storage.endpoint_url,
            },
        ),
        dataset_name=f"articles/{source_name}",
    )

    @dlt.resource(
        name="articles",
        write_disposition="replace",
        columns={
            "metadata": {"data_type": "text"},
            "published_at": {"data_type": "text"},
        },
    )
    def _resource():
        yield records

    load_info = pipeline.run(
        _resource(),
        loader_file_format="parquet",
    )

    logger.info("Bronze load complete for source=%s: %s", source_name, load_info)
    return len(records)
