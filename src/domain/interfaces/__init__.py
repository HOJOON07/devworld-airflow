from src.domain.interfaces.fetcher import FetchResult, Fetcher
from src.domain.interfaces.parser import ParsedArticle, Parser
from src.domain.interfaces.repository import (
    ArticleRepository,
    CrawlJobRepository,
    CrawlSourceRepository,
)
from src.domain.interfaces.storage import StorageAdapter

__all__ = [
    "ArticleRepository",
    "CrawlJobRepository",
    "CrawlSourceRepository",
    "FetchResult",
    "Fetcher",
    "ParsedArticle",
    "Parser",
    "StorageAdapter",
]
