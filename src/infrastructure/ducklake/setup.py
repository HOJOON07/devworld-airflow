from __future__ import annotations

import duckdb

from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def create_duckdb_connection(config: Config | None = None) -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection with httpfs configured for MinIO/R2.

    The connection uses httpfs extension to read parquet files from
    S3-compatible storage (MinIO in dev, R2 in prod).
    """
    if config is None:
        config = Config()

    storage = config.storage

    conn = duckdb.connect()

    conn.install_extension("httpfs")
    conn.load_extension("httpfs")

    conn.execute(f"SET s3_endpoint='{_strip_protocol(storage.endpoint_url)}'")
    conn.execute(f"SET s3_access_key_id='{storage.access_key}'")
    conn.execute(f"SET s3_secret_access_key='{storage.secret_key}'")
    conn.execute("SET s3_use_ssl=false")
    conn.execute("SET s3_url_style='path'")

    logger.info("DuckDB connection initialized with httpfs for %s", storage.endpoint_url)
    return conn


def setup_ducklake_catalog(
    conn: duckdb.DuckDBPyConnection, config: Config | None = None
) -> None:
    """Attach DuckLake catalog to the DuckDB connection.

    DuckLake uses PostgreSQL as the metadata catalog and R2/MinIO
    as the data storage (parquet files).
    """
    if config is None:
        config = Config()

    db = config.database
    storage = config.storage

    conn.install_extension("ducklake")
    conn.load_extension("ducklake")

    ducklake_dsn = (
        f"postgresql://{db.user}:{db.password}"
        f"@{db.host}:{db.port}/{db.name}"
    )

    conn.execute(
        f"""
        ATTACH '{ducklake_dsn}'
        AS ducklake (
            TYPE ducklake,
            DATA_PATH 's3://{storage.lake_bucket}/ducklake',
            METADATA_PATH '{ducklake_dsn}'
        )
        """
    )

    logger.info("DuckLake catalog attached (catalog=%s, data=s3://%s/ducklake)", db.name, storage.lake_bucket)


def _strip_protocol(endpoint_url: str) -> str:
    """Remove http:// or https:// prefix for DuckDB s3_endpoint setting."""
    for prefix in ("https://", "http://"):
        if endpoint_url.startswith(prefix):
            return endpoint_url[len(prefix):]
    return endpoint_url
