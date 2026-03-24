"""Unit tests for domain entities: Article, CrawlSource, CrawlJob."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.entities.article import Article
from src.domain.entities.crawl_job import CrawlJob
from src.domain.entities.crawl_source import CrawlSource

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class TestArticle:
    def test_create_with_required_fields(self):
        now = datetime.now(timezone.utc)
        article = Article(source_id="blog-a", url="https://a.com/1", discovered_at=now)

        assert article.source_id == "blog-a"
        assert article.url == "https://a.com/1"
        assert article.discovered_at == now
        assert article.id is not None  # auto-generated UUID

    def test_auto_generates_unique_ids(self):
        now = datetime.now(timezone.utc)
        a1 = Article(source_id="s", url="https://a.com/1", discovered_at=now)
        a2 = Article(source_id="s", url="https://a.com/2", discovered_at=now)
        assert a1.id != a2.id

    def test_optional_fields_default_to_none(self):
        now = datetime.now(timezone.utc)
        article = Article(source_id="s", url="https://a.com/1", discovered_at=now)

        assert article.title is None
        assert article.content_text is None
        assert article.content_html is None
        assert article.author is None
        assert article.published_at is None
        assert article.raw_storage_key is None
        assert article.content_hash is None
        assert article.metadata is None

    def test_create_with_all_fields(self, sample_article):
        assert sample_article.title == "Test Article Title"
        assert sample_article.content_text == "Raw HTML content"
        assert sample_article.content_html == "<p>Raw HTML content</p>"
        assert sample_article.author == "Test Author"
        assert sample_article.content_hash == "abc123hash"
        assert sample_article.metadata == {"tags": ["python", "data"]}


# ---------------------------------------------------------------------------
# CrawlSource
# ---------------------------------------------------------------------------


class TestCrawlSource:
    def test_create_with_required_fields(self):
        source = CrawlSource(name="Blog A", source_type="blog", base_url="https://a.com")

        assert source.name == "Blog A"
        assert source.source_type == "blog"
        assert source.base_url == "https://a.com"
        assert source.id is not None

    def test_defaults(self):
        source = CrawlSource(name="Blog A", source_type="blog", base_url="https://a.com")

        assert source.is_active is True
        assert source.feed_url is None
        assert source.crawl_config is None
        assert isinstance(source.created_at, datetime)

    def test_create_with_config(self, sample_crawl_source):
        assert sample_crawl_source.name == "Example Tech Blog"
        assert sample_crawl_source.feed_url == "https://example.com/blog/rss"
        assert "selectors" in sample_crawl_source.crawl_config


# ---------------------------------------------------------------------------
# CrawlJob
# ---------------------------------------------------------------------------


class TestCrawlJob:
    def test_create_with_defaults(self):
        job = CrawlJob(source_id="blog-a", partition_date="2026-03-24")

        assert job.source_id == "blog-a"
        assert job.partition_date == "2026-03-24"
        assert job.status == "pending"
        assert job.discovered_count == 0
        assert job.fetched_count == 0
        assert job.parsed_count == 0
        assert job.error_message is None
        assert job.started_at is None
        assert job.completed_at is None

    def test_status_can_be_set(self):
        job = CrawlJob(source_id="s", partition_date="2026-03-24")

        job.status = "running"
        assert job.status == "running"

        job.status = "completed"
        assert job.status == "completed"

    def test_status_transition_with_timestamps(self):
        job = CrawlJob(source_id="s", partition_date="2026-03-24")
        assert job.status == "pending"

        now = datetime.now(timezone.utc)
        job.status = "running"
        job.started_at = now
        assert job.started_at is not None

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        assert job.completed_at >= job.started_at

    def test_error_state(self):
        job = CrawlJob(source_id="s", partition_date="2026-03-24")
        job.status = "failed"
        job.error_message = "Connection timeout"

        assert job.status == "failed"
        assert job.error_message == "Connection timeout"

    def test_counter_fields(self):
        job = CrawlJob(source_id="s", partition_date="2026-03-24")

        job.discovered_count = 10
        job.fetched_count = 8
        job.parsed_count = 7

        assert job.discovered_count == 10
        assert job.fetched_count == 8
        assert job.parsed_count == 7
