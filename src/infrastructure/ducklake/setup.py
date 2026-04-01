"""DuckLake connection utility.

Creates a DuckDB in-memory connection with DuckLake attached.
Used by enrich_service and scripts/duckdb-ui.py.
"""

from __future__ import annotations

import duckdb

from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def create_ducklake_connection(config: Config | None = None) -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection with DuckLake and S3 configured.

    Args:
        config: Application config. Defaults to Config() if not provided.

    Returns:
        DuckDB connection with DuckLake attached as 'lake'.
    """
    if config is None:
        config = Config()

    conn = duckdb.connect(":memory:")

    # Install and load extensions
    for ext in ["postgres", "httpfs", "ducklake"]:
        conn.install_extension(ext)
        conn.load_extension(ext)

    # Configure S3 for MinIO/R2
    storage = config.storage
    endpoint = _strip_protocol(storage.endpoint_url)
    conn.execute(f"SET s3_endpoint='{_esc(endpoint)}'")
    conn.execute(f"SET s3_access_key_id='{_esc(storage.access_key)}'")
    conn.execute(f"SET s3_secret_access_key='{_esc(storage.secret_key)}'")
    conn.execute(f"SET s3_use_ssl={'true' if storage.use_ssl else 'false'}")
    conn.execute("SET s3_url_style='path'")

    # Attach DuckLake — ducklake:postgres: + libpq params
    catalog_url = _esc(config.ducklake.catalog_url)
    data_path = _esc(config.ducklake.data_path)
    conn.execute(
        f"ATTACH 'ducklake:postgres:{catalog_url}' AS devworld_lake (DATA_PATH '{data_path}', METADATA_SCHEMA 'devworld_lake')"
    )

    logger.info(
        "DuckLake connection ready (data=%s)",
        data_path,
    )
    return conn


def _esc(value: str) -> str:
    """Escape single quotes for safe SQL string interpolation."""
    return value.replace("'", "''")


def _strip_protocol(endpoint_url: str) -> str:
    """Remove http:// or https:// prefix for DuckDB s3_endpoint setting."""
    for prefix in ("https://", "http://"):
        if endpoint_url.startswith(prefix):
            return endpoint_url[len(prefix):]
    return endpoint_url
