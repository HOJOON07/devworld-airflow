from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import httpx

from src.shared.logging import setup_logging

logger = setup_logging(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


class GitHubAPIClient:
    def __init__(
        self,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._timeout = timeout
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        url = f"{GITHUB_API_BASE}{path}"
        with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
            response = client.get(url, params=params)
            self._log_rate_limit(response)
            response.raise_for_status()
            return response

    def _get_paginated(
        self, path: str, params: dict | None = None, max_pages: int = 10
    ) -> list[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        params.setdefault("page", 1)

        all_items: list[dict] = []
        for _ in range(max_pages):
            resp = self._get(path, params=params)
            items = resp.json()
            if not items:
                break
            all_items.extend(items)

            next_url = self._parse_next_link(resp.headers.get("link", ""))
            if not next_url:
                break
            parsed = urlparse(next_url)
            qs = parse_qs(parsed.query)
            params["page"] = int(qs.get("page", [str(int(params["page"]) + 1)])[0])

        return all_items

    def list_prs(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        sort: str = "updated",
        per_page: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        logger.info("Listing PRs for %s/%s state=%s sort=%s", owner, repo, state, sort)
        return self._get_paginated(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "sort": sort, "direction": "desc", "per_page": per_page},
            max_pages=max_pages,
        )

    def get_pr(self, owner: str, repo: str, number: int) -> dict:
        logger.info("Getting PR %s/%s#%d", owner, repo, number)
        return self._get(f"/repos/{owner}/{repo}/pulls/{number}").json()

    def list_pr_files(self, owner: str, repo: str, number: int) -> list[dict]:
        logger.info("Listing files for PR %s/%s#%d", owner, repo, number)
        return self._get_paginated(
            f"/repos/{owner}/{repo}/pulls/{number}/files",
            max_pages=3,
        )

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        sort: str = "updated",
        since: str | None = None,
        per_page: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        logger.info(
            "Listing issues for %s/%s state=%s sort=%s since=%s",
            owner, repo, state, sort, since,
        )
        params: dict = {"state": state, "sort": sort, "per_page": per_page}
        if since:
            params["since"] = since
        return self._get_paginated(
            f"/repos/{owner}/{repo}/issues",
            params=params,
            max_pages=max_pages,
        )

    def _log_rate_limit(self, response: httpx.Response) -> None:
        remaining = response.headers.get("x-ratelimit-remaining")
        limit = response.headers.get("x-ratelimit-limit")
        if remaining is not None:
            logger.info("GitHub API rate limit: %s/%s remaining", remaining, limit)
            if int(remaining) < 100:
                logger.warning(
                    "GitHub API rate limit low: %s/%s remaining", remaining, limit
                )

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None
