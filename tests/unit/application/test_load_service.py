"""Unit tests for application load_service: dlt bronze article loading."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.application.load_service import (
    _fetch_articles_by_source,
    load_articles_to_bronze,
)
from src.shared.config import Config, DatabaseConfig, StorageConfig

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**storage_overrides) -> Config:
    """Build a Config with optional StorageConfig overrides."""
    return Config(
        storage=StorageConfig(**storage_overrides) if storage_overrides else StorageConfig(),
        database=DatabaseConfig(),
    )


def _mock_engine_with_rows(mock_create_engine: MagicMock, rows: list[dict]) -> None:
    """Wire up a mock create_engine to return the given rows."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.mappings.return_value.all.return_value = rows
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_create_engine.return_value = mock_engine


# ---------------------------------------------------------------------------
# _fetch_articles_by_source
# ---------------------------------------------------------------------------


class TestFetchArticlesBySource:
    """Tests for the internal _fetch_articles_by_source helper."""

    @patch("src.application.load_service.create_engine")
    def test_returns_records_with_extra_columns(self, mock_create_engine):
        """Each returned record should include partition_date and crawled_at."""
        fake_row = {
            "id": "art-1",
            "source_id": "src-1",
            "source_name": "Test Blog",
            "url": "https://example.com/1",
            "title": "Title",
            "content_text": "text",
            "content_html": "<p>text</p>",
            "author": "Author",
            "published_at": datetime(2026, 3, 24, tzinfo=timezone.utc),
            "discovered_at": datetime(2026, 3, 24, tzinfo=timezone.utc),
            "raw_storage_key": "raw/src-1/2026-03-24/abc.html",
            "content_hash": "hash123",
            "metadata": None,
        }
        _mock_engine_with_rows(mock_create_engine, [fake_row])

        records = _fetch_articles_by_source(
            database_url="postgresql://test:test@localhost/test",
            source_name="Test Blog",
            partition_date="2026-03-24",
        )

        assert len(records) == 1
        assert records[0]["partition_date"] == "2026-03-24"
        assert "crawled_at" in records[0]
        assert records[0]["id"] == "art-1"
        assert records[0]["source_name"] == "Test Blog"

    @patch("src.application.load_service.create_engine")
    def test_empty_query_returns_empty_list(self, mock_create_engine):
        """When no articles match, an empty list should be returned."""
        _mock_engine_with_rows(mock_create_engine, [])

        records = _fetch_articles_by_source(
            database_url="postgresql://test:test@localhost/test",
            source_name="Empty Blog",
            partition_date="2026-03-25",
        )

        assert records == []

    @patch("src.application.load_service.create_engine")
    def test_passes_source_name_as_bind_param(self, mock_create_engine):
        """The SQL query should filter by source_name."""
        _mock_engine_with_rows(mock_create_engine, [])

        _fetch_articles_by_source(
            database_url="postgresql://test:test@localhost/test",
            source_name="My Blog",
            partition_date="2026-03-24",
        )

        mock_conn = mock_create_engine.return_value.connect.return_value.__enter__()
        call_args = mock_conn.execute.call_args
        bind_params = call_args[0][1]
        assert bind_params["source_name"] == "My Blog"
        assert bind_params["partition_date"] == "2026-03-24"

    @patch("src.application.load_service.create_engine")
    def test_multiple_rows(self, mock_create_engine):
        """Should return all rows from the query."""
        rows = [
            {"id": f"art-{i}", "source_id": "s1", "source_name": "Blog",
             "url": f"https://example.com/{i}", "title": f"T{i}",
             "content_text": "t", "content_html": "<p>t</p>", "author": "A",
             "published_at": None, "discovered_at": datetime(2026, 3, 24, tzinfo=timezone.utc),
             "raw_storage_key": f"raw/s1/2026-03-24/{i}.html", "content_hash": f"h{i}",
             "metadata": None}
            for i in range(5)
        ]
        _mock_engine_with_rows(mock_create_engine, rows)

        records = _fetch_articles_by_source(
            database_url="postgresql://test:test@localhost/test",
            source_name="Blog",
            partition_date="2026-03-24",
        )

        assert len(records) == 5
        for r in records:
            assert "partition_date" in r
            assert "crawled_at" in r


# ---------------------------------------------------------------------------
# load_articles_to_bronze
# ---------------------------------------------------------------------------


class TestLoadArticlesToBronze:
    """Tests for the main load_articles_to_bronze orchestration function."""

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_returns_zero_for_empty_data(self, mock_fetch, mock_dlt):
        """When no articles are found, should return 0 without calling dlt."""
        mock_fetch.return_value = []

        result = load_articles_to_bronze(
            config=_make_config(),
            source_name="Empty Blog",
            partition_date="2026-03-25",
        )

        assert result == 0
        mock_dlt.pipeline.assert_not_called()

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_returns_article_count(self, mock_fetch, mock_dlt):
        """Should return the number of articles loaded."""
        mock_fetch.return_value = [
            {"id": "a1", "partition_date": "2026-03-24"},
            {"id": "a2", "partition_date": "2026-03-24"},
            {"id": "a3", "partition_date": "2026-03-24"},
        ]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = "LoadInfo(ok)"
        mock_dlt.pipeline.return_value = mock_pipeline

        result = load_articles_to_bronze(
            config=_make_config(),
            source_name="Blog",
            partition_date="2026-03-24",
        )

        assert result == 3

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_creates_pipeline_with_correct_name_and_dataset(self, mock_fetch, mock_dlt):
        """Pipeline should use 'bronze_articles' name and partition-based dataset."""
        mock_fetch.return_value = [{"id": "a1"}]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = "ok"
        mock_dlt.pipeline.return_value = mock_pipeline

        load_articles_to_bronze(
            config=_make_config(),
            source_name="Blog",
            partition_date="2026-03-24",
        )

        mock_dlt.pipeline.assert_called_once()
        call_kwargs = mock_dlt.pipeline.call_args.kwargs
        assert call_kwargs["pipeline_name"] == "bronze_articles"
        assert call_kwargs["dataset_name"] == "articles/2026-03-24"

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_uses_parquet_format(self, mock_fetch, mock_dlt):
        """Pipeline.run should be called with loader_file_format='parquet'."""
        mock_fetch.return_value = [{"id": "a1"}]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = "ok"
        mock_dlt.pipeline.return_value = mock_pipeline

        load_articles_to_bronze(
            config=_make_config(),
            source_name="Blog",
            partition_date="2026-03-24",
        )

        mock_pipeline.run.assert_called_once()
        run_kwargs = mock_pipeline.run.call_args.kwargs
        assert run_kwargs["loader_file_format"] == "parquet"

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_filesystem_destination_uses_storage_config(self, mock_fetch, mock_dlt):
        """Filesystem destination should use storage config credentials and bronze bucket."""
        mock_fetch.return_value = [{"id": "a1"}]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = "ok"
        mock_dlt.pipeline.return_value = mock_pipeline

        config = Config(
            storage=StorageConfig(
                endpoint_url="http://minio:9000",
                access_key="mykey",
                secret_key="mysecret",
                bronze_bucket="my-bronze",
            ),
            database=DatabaseConfig(),
        )

        load_articles_to_bronze(
            config=config,
            source_name="Blog",
            partition_date="2026-03-24",
        )

        mock_dlt.destinations.filesystem.assert_called_once_with(
            bucket_url="s3://my-bronze",
            credentials={
                "aws_access_key_id": "mykey",
                "aws_secret_access_key": "mysecret",
                "endpoint_url": "http://minio:9000",
            },
        )

    @patch("src.application.load_service.dlt")
    @patch("src.application.load_service._fetch_articles_by_source")
    def test_passes_source_name_to_fetch(self, mock_fetch, mock_dlt):
        """load_articles_to_bronze should pass source_name through to _fetch_articles_by_source."""
        mock_fetch.return_value = []

        load_articles_to_bronze(
            config=_make_config(),
            source_name="Specific Blog",
            partition_date="2026-03-24",
        )

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[0][1] == "Specific Blog"  # second positional arg
        assert call_args[0][2] == "2026-03-24"  # third positional arg
