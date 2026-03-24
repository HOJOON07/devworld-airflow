"""Unit tests for application services: DiscoveryService, FetchService, ParseService."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.discovery_service import DiscoveryService
from src.application.fetch_service import FetchService
from src.application.parse_service import ParseService
from src.domain.entities.article import Article
from src.domain.entities.crawl_source import CrawlSource
from src.domain.interfaces.fetcher import FetchResult
from src.domain.interfaces.parser import ParsedArticle

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Stubs implementing the protocols for unit testing
# ---------------------------------------------------------------------------


class StubFetcher:
    """Returns canned FetchResult for any URL."""

    def __init__(self, content: str = "<html>stub</html>") -> None:
        self._content = content
        self.fetched_urls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.fetched_urls.append(url)
        return FetchResult(url=url, status_code=200, content=self._content)


class StubParser:
    """Returns canned ParsedArticle list."""

    def __init__(self, articles: list[ParsedArticle] | None = None) -> None:
        self._articles = articles or []

    def parse(self, raw_content: str, source_type: str) -> list[ParsedArticle]:
        return self._articles


class StubArticleRepo:
    """In-memory article repository."""

    def __init__(self) -> None:
        self.articles: dict[str, Article] = {}
        self._known_urls: set[str] = set()

    def save(self, article: Article) -> None:
        self.articles[article.id] = article
        self._known_urls.add(article.url)

    def find_by_id(self, article_id: str) -> Article | None:
        return self.articles.get(article_id)

    def find_by_url(self, url: str) -> Article | None:
        for a in self.articles.values():
            if a.url == url:
                return a
        return None

    def find_by_source(self, source_id: str) -> list[Article]:
        return [a for a in self.articles.values() if a.source_id == source_id]

    def exists_by_url(self, url: str) -> bool:
        return url in self._known_urls

    def seed_known_url(self, url: str) -> None:
        self._known_urls.add(url)


class StubStorage:
    """In-memory storage adapter."""

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


# ---------------------------------------------------------------------------
# DiscoveryService
# ---------------------------------------------------------------------------


class TestDiscoveryService:
    def _make_source(self, **kwargs) -> CrawlSource:
        defaults = dict(
            name="Test Blog",
            source_type="rss",
            base_url="https://example.com",
            feed_url="https://example.com/rss",
        )
        defaults.update(kwargs)
        return CrawlSource(**defaults)

    def test_discover_returns_new_urls(self):
        parsed_articles = [
            ParsedArticle(url="https://example.com/1"),
            ParsedArticle(url="https://example.com/2"),
            ParsedArticle(url="https://example.com/3"),
        ]
        fetcher = StubFetcher()
        parser = StubParser(articles=parsed_articles)
        repo = StubArticleRepo()

        service = DiscoveryService(fetcher=fetcher, parser=parser, article_repo=repo)
        source = self._make_source()
        new_urls = service.discover(source)

        assert len(new_urls) == 3
        assert "https://example.com/1" in new_urls

    def test_discover_filters_existing_urls(self):
        parsed_articles = [
            ParsedArticle(url="https://example.com/1"),
            ParsedArticle(url="https://example.com/2"),
        ]
        fetcher = StubFetcher()
        parser = StubParser(articles=parsed_articles)
        repo = StubArticleRepo()
        repo.seed_known_url("https://example.com/1")

        service = DiscoveryService(fetcher=fetcher, parser=parser, article_repo=repo)
        source = self._make_source()
        new_urls = service.discover(source)

        assert new_urls == ["https://example.com/2"]

    def test_discover_uses_feed_url_when_available(self):
        fetcher = StubFetcher()
        parser = StubParser()
        repo = StubArticleRepo()

        service = DiscoveryService(fetcher=fetcher, parser=parser, article_repo=repo)
        source = self._make_source(feed_url="https://example.com/rss")
        service.discover(source)

        assert fetcher.fetched_urls == ["https://example.com/rss"]

    def test_discover_falls_back_to_base_url(self):
        fetcher = StubFetcher()
        parser = StubParser()
        repo = StubArticleRepo()

        service = DiscoveryService(fetcher=fetcher, parser=parser, article_repo=repo)
        source = self._make_source(feed_url=None)
        service.discover(source)

        assert fetcher.fetched_urls == ["https://example.com"]


# ---------------------------------------------------------------------------
# FetchService
# ---------------------------------------------------------------------------


class TestFetchService:
    def test_fetch_and_store_saves_raw_content(self):
        fetcher = StubFetcher(content="<html>page</html>")
        storage = StubStorage()
        repo = StubArticleRepo()

        service = FetchService(
            fetcher=fetcher,
            storage=storage,
            article_repo=repo,
            raw_bucket="test-raw",
        )
        articles = service.fetch_and_store(
            urls=["https://example.com/a"],
            source_id="blog-a",
            partition_date="2026-03-24",
        )

        assert len(articles) == 1
        assert articles[0].source_id == "blog-a"
        assert articles[0].raw_storage_key is not None
        # Verify raw content was stored
        stored = storage.get_object("test-raw", articles[0].raw_storage_key)
        assert stored == b"<html>page</html>"

    def test_fetch_and_store_saves_to_repo(self):
        fetcher = StubFetcher()
        storage = StubStorage()
        repo = StubArticleRepo()

        service = FetchService(
            fetcher=fetcher, storage=storage, article_repo=repo, raw_bucket="raw"
        )
        articles = service.fetch_and_store(
            urls=["https://example.com/1", "https://example.com/2"],
            source_id="s",
            partition_date="2026-03-24",
        )

        assert len(articles) == 2
        assert len(repo.articles) == 2

    def test_fetch_and_store_continues_on_error(self):
        """If one URL fails, the service should still process remaining URLs."""

        class FailOnceFetcher:
            def __init__(self):
                self._call_count = 0

            def fetch(self, url: str) -> FetchResult:
                self._call_count += 1
                if self._call_count == 1:
                    raise ConnectionError("Network error")
                return FetchResult(url=url, status_code=200, content="ok")

        fetcher = FailOnceFetcher()
        storage = StubStorage()
        repo = StubArticleRepo()

        service = FetchService(
            fetcher=fetcher, storage=storage, article_repo=repo, raw_bucket="raw"
        )
        articles = service.fetch_and_store(
            urls=["https://fail.com", "https://ok.com"],
            source_id="s",
            partition_date="2026-03-24",
        )

        assert len(articles) == 1
        assert articles[0].url == "https://ok.com"

    def test_storage_key_is_deterministic(self):
        key1 = FetchService._build_storage_key("blog-a", "2026-03-24", "https://a.com/1")
        key2 = FetchService._build_storage_key("blog-a", "2026-03-24", "https://a.com/1")
        assert key1 == key2
        assert key1.startswith("raw/blog-a/2026-03-24/")
        assert key1.endswith(".html")


# ---------------------------------------------------------------------------
# ParseService
# ---------------------------------------------------------------------------


class TestParseService:
    def _make_article_with_raw(self, storage: StubStorage, raw_content: str) -> Article:
        now = datetime.now(timezone.utc)
        article = Article(
            source_id="blog-a",
            url="https://example.com/post",
            discovered_at=now,
            raw_storage_key="raw/blog-a/2026-03-24/abc.html",
        )
        storage.put_object("test-raw", article.raw_storage_key, raw_content.encode())
        return article

    def test_parse_articles_enriches_fields(self):
        storage = StubStorage()
        repo = StubArticleRepo()
        parsed = ParsedArticle(
            url="https://example.com/post",
            title="Parsed Title",
            content_text="Parsed text content",
            content_html="<p>Parsed text content</p>",
            author="Author",
        )
        parser = StubParser(articles=[parsed])

        article = self._make_article_with_raw(storage, "<html>raw</html>")

        service = ParseService(
            parser=parser, storage=storage, article_repo=repo, raw_bucket="test-raw"
        )
        result = service.parse_articles([article], source_type="rss")

        assert len(result) == 1
        assert result[0].title == "Parsed Title"
        assert result[0].content_text == "Parsed text content"
        assert result[0].author == "Author"

    def test_parse_articles_computes_content_hash(self):
        storage = StubStorage()
        repo = StubArticleRepo()
        parsed = ParsedArticle(
            url="https://example.com/post",
            content_text="Some text",
        )
        parser = StubParser(articles=[parsed])

        article = self._make_article_with_raw(storage, "<html>raw</html>")

        service = ParseService(
            parser=parser, storage=storage, article_repo=repo, raw_bucket="test-raw"
        )
        result = service.parse_articles([article], source_type="rss")

        assert result[0].content_hash is not None
        assert len(result[0].content_hash) == 64  # SHA-256

    def test_skips_articles_without_storage_key(self):
        storage = StubStorage()
        repo = StubArticleRepo()
        parser = StubParser()

        article = Article(
            source_id="s",
            url="https://a.com",
            discovered_at=datetime.now(timezone.utc),
            raw_storage_key=None,
        )

        service = ParseService(
            parser=parser, storage=storage, article_repo=repo, raw_bucket="raw"
        )
        result = service.parse_articles([article], source_type="rss")

        assert len(result) == 0

    def test_skips_articles_with_no_parsed_result(self):
        storage = StubStorage()
        repo = StubArticleRepo()
        parser = StubParser(articles=[])  # returns empty

        article = self._make_article_with_raw(storage, "<html>raw</html>")

        service = ParseService(
            parser=parser, storage=storage, article_repo=repo, raw_bucket="test-raw"
        )
        result = service.parse_articles([article], source_type="rss")

        assert len(result) == 0
