from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class StorageConfig:
    endpoint_url: str = field(
        default_factory=lambda: os.environ.get(
            "STORAGE_ENDPOINT_URL", "http://localhost:9000"
        )
    )
    access_key: str = field(
        default_factory=lambda: os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
    )
    secret_key: str = field(
        default_factory=lambda: os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
    )
    raw_bucket: str = field(
        default_factory=lambda: os.environ.get("RAW_BUCKET", "devworld-raw")
    )
    lake_bucket: str = field(
        default_factory=lambda: os.environ.get("LAKE_BUCKET", "devworld-lake")
    )
    bronze_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "STORAGE_BRONZE_BUCKET", "devworld-bronze"
        )
    )
    silver_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "STORAGE_SILVER_BUCKET", "devworld-silver"
        )
    )
    gold_analytics_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "STORAGE_GOLD_ANALYTICS_BUCKET", "devworld-gold-analytics"
        )
    )
    region: str = field(
        default_factory=lambda: os.environ.get("STORAGE_REGION", "auto")
    )

    @property
    def use_ssl(self) -> bool:
        """Determine SSL based on endpoint URL protocol. R2 uses https, MinIO uses http."""
        return self.endpoint_url.startswith("https://")


@dataclass
class DatabaseConfig:
    host: str = field(
        default_factory=lambda: os.environ.get("DB_HOST", "localhost")
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("DB_PORT", "5432"))
    )
    name: str = field(
        default_factory=lambda: os.environ.get("DB_NAME", "devworld")
    )
    user: str = field(
        default_factory=lambda: os.environ.get("DB_USER", "devworld")
    )
    password: str = field(
        default_factory=lambda: os.environ.get("DB_PASSWORD", "devworld")
    )

    @property
    def url(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass
class DuckLakeConfig:
    """DuckLake configuration.

    catalog_url: libpq format for DuckDB ATTACH (host=... port=... dbname=...)
    data_path: S3 path for DuckLake parquet files
    """
    catalog_url: str = field(
        default_factory=lambda: os.environ.get(
            "DUCKLAKE_CATALOG_URL",
            "host=localhost port=5432 dbname=airflow_db user=airflow password=airflow",
        )
    )
    data_path: str = field(
        default_factory=lambda: os.environ.get(
            "DUCKLAKE_DATA_PATH", "s3://devworld-lake"
        )
    )

    @property
    def catalog_connection_url(self) -> str:
        """Convert libpq format to postgres:// URL for dlt DuckLakeCredentials."""
        parts = dict(p.split("=", 1) for p in self.catalog_url.split() if "=" in p)
        user = parts.get("user", "airflow")
        password = parts.get("password", "airflow")
        host = parts.get("host", "localhost")
        port = parts.get("port", "5432")
        dbname = parts.get("dbname", "airflow_db")
        return f"postgres://{user}:{password}@{host}:{port}/{dbname}"


@dataclass
class Config:
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ducklake: DuckLakeConfig = field(default_factory=DuckLakeConfig)
    environment: str = field(
        default_factory=lambda: os.environ.get("ENVIRONMENT", "dev")
    )
