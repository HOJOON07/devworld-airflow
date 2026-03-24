"""Unit tests for configuration loading."""

from __future__ import annotations

import os

import pytest

from src.shared.config import Config, DatabaseConfig, StorageConfig

pytestmark = pytest.mark.unit


class TestStorageConfig:
    def test_defaults(self):
        config = StorageConfig()
        assert config.endpoint_url == os.environ.get("STORAGE_ENDPOINT_URL", "http://localhost:9000")
        assert config.raw_bucket == os.environ.get("RAW_BUCKET", "devworld-raw")
        assert config.lake_bucket == os.environ.get("LAKE_BUCKET", "devworld-lake")

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("STORAGE_ENDPOINT_URL", "https://custom-s3.example.com")
        monkeypatch.setenv("RAW_BUCKET", "my-raw")
        monkeypatch.setenv("LAKE_BUCKET", "my-lake")

        config = StorageConfig()
        assert config.endpoint_url == "https://custom-s3.example.com"
        assert config.raw_bucket == "my-raw"
        assert config.lake_bucket == "my-lake"


class TestDatabaseConfig:
    def test_defaults(self):
        config = DatabaseConfig()
        assert config.host == os.environ.get("DB_HOST", "localhost")
        assert config.port == int(os.environ.get("DB_PORT", "5432"))
        assert config.name == os.environ.get("DB_NAME", "devworld")

    def test_url_property(self):
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            name="testdb",
            user="testuser",
            password="testpass",
        )
        assert config.url == "postgresql://testuser:testpass@db.example.com:5433/testdb"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "remote-db.example.com")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "custom_db")
        monkeypatch.setenv("DB_USER", "admin")
        monkeypatch.setenv("DB_PASSWORD", "secret")

        config = DatabaseConfig()
        assert config.host == "remote-db.example.com"
        assert config.port == 5433
        assert config.url == "postgresql://admin:secret@remote-db.example.com:5433/custom_db"


class TestConfig:
    def test_default_environment(self):
        config = Config()
        assert config.environment == os.environ.get("ENVIRONMENT", "dev")

    def test_nested_configs(self):
        config = Config()
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.database, DatabaseConfig)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        config = Config()
        assert config.environment == "production"
