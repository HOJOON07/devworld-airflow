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
        default_factory=lambda: os.environ.get("STORAGE_REGION", "us-east-1")
    )


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
class Config:
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    environment: str = field(
        default_factory=lambda: os.environ.get("ENVIRONMENT", "dev")
    )
