from __future__ import annotations

import httpx

from src.domain.interfaces.fetcher import FetchResult
from src.shared.logging import setup_logging

logger = setup_logging(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


class HttpFetcher:
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._headers = {**DEFAULT_HEADERS, **(headers or {})}

    def fetch(self, url: str) -> FetchResult:
        logger.info("Fetching url=%s", url)
        with httpx.Client(timeout=self._timeout, headers=self._headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        return FetchResult(
            url=url,
            status_code=response.status_code,
            content=response.text,
            content_type=response.headers.get("content-type"),
            headers=dict(response.headers),
        )
