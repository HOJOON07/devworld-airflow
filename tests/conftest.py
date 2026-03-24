"""
Root conftest.py — shared fixtures for the devworld-airflow test suite.

Fixtures defined here are available to all tests under tests/.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.entities.article import Article
from src.domain.entities.crawl_job import CrawlJob
from src.domain.entities.crawl_source import CrawlSource


# ---------------------------------------------------------------------------
# Marker registration (also declared in pyproject.toml)
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: integration tests (may require Airflow, DB, etc.)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Domain entity fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_article() -> Article:
    return Article(
        source_id="techblog-example",
        url="https://example.com/blog/test-article",
        discovered_at=_utcnow(),
        title="Test Article Title",
        content_text="Raw HTML content",
        content_html="<p>Raw HTML content</p>",
        author="Test Author",
        published_at=_utcnow(),
        content_hash="abc123hash",
        metadata={"tags": ["python", "data"]},
    )


@pytest.fixture()
def sample_crawl_source() -> CrawlSource:
    return CrawlSource(
        name="Example Tech Blog",
        source_type="blog",
        base_url="https://example.com/blog",
        feed_url="https://example.com/blog/rss",
        crawl_config={"selectors": {"title": "h1.post-title", "body": "div.post-body"}},
        is_active=True,
    )


@pytest.fixture()
def sample_crawl_job() -> CrawlJob:
    return CrawlJob(
        source_id="techblog-example",
        partition_date="2026-03-24",
    )


# ---------------------------------------------------------------------------
# Storage fixtures
# ---------------------------------------------------------------------------


class InMemoryStorageAdapter:
    """Simple in-memory storage adapter for testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, bytes]] = {}

    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        self._store.setdefault(bucket, {})[key] = data

    def get_object(self, bucket: str, key: str) -> bytes:
        return self._store[bucket][key]

    def list_objects(self, bucket: str, prefix: str) -> list[str]:
        if bucket not in self._store:
            return []
        return [k for k in self._store[bucket] if k.startswith(prefix)]


@pytest.fixture()
def mock_storage() -> InMemoryStorageAdapter:
    return InMemoryStorageAdapter()


@pytest.fixture()
def temp_storage_dir(tmp_path):
    """Provides a temporary directory for tests that need file-based storage."""
    storage = tmp_path / "storage"
    storage.mkdir()
    return storage
