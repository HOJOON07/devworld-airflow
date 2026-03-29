"""GitHub Collect Service — fetches PRs and Issues from GitHub API.

Raw First: API JSON을 MinIO에 저장한 후 파싱 결과를 PostgreSQL에 적재.
Pipeline: GitHub API → Raw JSON (MinIO) + PostgreSQL → AI Enrich → dbt Gold
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from src.domain.entities.github_issue import GitHubIssue
from src.domain.entities.github_pr import GitHubPR
from src.domain.entities.github_repo import GitHubRepo
from src.infrastructure.github.github_api_client import GitHubAPIClient
from src.infrastructure.github.github_repository import (
    GitHubIssueRepository,
    GitHubPRFilesRepository,
    GitHubPRRepository,
    GitHubRepoRepository,
)
from src.infrastructure.storage.s3_storage import S3Storage
from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)

MAX_PATCH_FILES = 10
LINKED_PR_PATTERN = re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE)


# ============================================================
# Public API
# ============================================================

def collect_repo(
    config: Config,
    repo: GitHubRepo,
    initial_fetch_days: int = 14,
) -> dict:
    """Collect PRs and Issues for a single GitHub repo.

    Raw First: API JSON → MinIO, 파싱 결과 → PostgreSQL.
    Returns: {"prs_collected": int, "issues_collected": int}
    """
    api = GitHubAPIClient()
    repos = _build_repositories(config.database.url)
    storage = S3Storage(config.storage)
    raw_bucket = config.storage.raw_bucket

    watermark = repo.last_collected_at
    if watermark is None:
        watermark = datetime.now(timezone.utc) - timedelta(days=initial_fetch_days)

    since_iso = watermark.strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    prs_collected = _collect_prs(api, repos, storage, raw_bucket, repo, since_iso, date_str)
    issues_collected = _collect_issues(api, repos, storage, raw_bucket, repo, since_iso, date_str)

    repos["repo"].update_last_collected(repo.id, now)

    summary = {"prs_collected": prs_collected, "issues_collected": issues_collected}
    logger.info("Collection complete for %s: %s", repo.full_name, summary)
    return summary


# ============================================================
# PR Collection
# ============================================================

def _collect_prs(
    api: GitHubAPIClient,
    repos: dict,
    storage: S3Storage,
    raw_bucket: str,
    repo: GitHubRepo,
    since_iso: str,
    date_str: str,
) -> int:
    raw_prs = api.list_prs(repo.owner, repo.name, state="all", sort="updated")
    collected = 0
    repo_key = f"{repo.owner}_{repo.name}"

    for raw_pr in raw_prs:
        pr_updated = raw_pr.get("updated_at", "")
        if pr_updated and pr_updated < since_iso:
            break

        try:
            # Raw First: API JSON을 MinIO에 저장
            raw_key = f"raw/github/{repo_key}/{date_str}/pr_{raw_pr['number']}.json"
            storage.put_object(raw_bucket, raw_key, json.dumps(raw_pr, ensure_ascii=False).encode())

            pr_entity = _parse_pr(repo, raw_pr)
            pr_entity.raw_storage_key = raw_key
            file_records = _collect_pr_files(api, repo, raw_pr["number"])

            # diff_text = 상위 10개 파일 patch 합침
            pr_entity.diff_text = _build_diff_text(file_records)

            repos["pr"].save(pr_entity)
            repos["pr_files"].save_batch(pr_entity.id, file_records)
            collected += 1
        except Exception:
            logger.exception("Failed to collect PR #%s for %s", raw_pr.get("number"), repo.full_name)

    logger.info("Collected %d PRs for %s", collected, repo.full_name)
    return collected


def _collect_pr_files(
    api: GitHubAPIClient,
    repo: GitHubRepo,
    pr_number: int,
) -> list[dict]:
    raw_files = api.list_pr_files(repo.owner, repo.name, pr_number)
    records = []

    for i, f in enumerate(raw_files):
        records.append({
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
            "patch": f.get("patch") if i < MAX_PATCH_FILES else None,
        })

    return records


def _build_diff_text(file_records: list[dict]) -> str | None:
    parts = []
    for f in file_records:
        if f.get("patch"):
            parts.append(f"--- {f['filename']} ---\n{f['patch']}")
    return "\n\n".join(parts) if parts else None


def _parse_pr(repo: GitHubRepo, raw: dict) -> GitHubPR:
    state = raw.get("state", "open")
    if raw.get("merged_at"):
        state = "merged"

    return GitHubPR(
        repo_id=repo.id,
        pr_number=raw["number"],
        title=raw.get("title", ""),
        body=raw.get("body"),
        state=state,
        author=raw.get("user", {}).get("login", ""),
        labels=[l["name"] for l in raw.get("labels", [])],
        created_at=_parse_dt(raw.get("created_at")),
        updated_at=_parse_dt(raw.get("updated_at")),
        merged_at=_parse_dt(raw.get("merged_at")),
        diff_text=None,
        raw_storage_key=None,
        metadata={
            "html_url": raw.get("html_url"),
            "base_ref": raw.get("base", {}).get("ref"),
            "head_ref": raw.get("head", {}).get("ref"),
        },
    )


# ============================================================
# Issue Collection
# ============================================================

def _collect_issues(
    api: GitHubAPIClient,
    repos: dict,
    storage: S3Storage,
    raw_bucket: str,
    repo: GitHubRepo,
    since_iso: str,
    date_str: str,
) -> int:
    raw_issues = api.list_issues(
        repo.owner, repo.name, state="all", sort="updated", since=since_iso,
    )
    collected = 0
    repo_key = f"{repo.owner}_{repo.name}"

    for raw_issue in raw_issues:
        if raw_issue.get("pull_request"):
            continue

        try:
            # Raw First: API JSON을 MinIO에 저장
            raw_key = f"raw/github/{repo_key}/{date_str}/issue_{raw_issue['number']}.json"
            storage.put_object(raw_bucket, raw_key, json.dumps(raw_issue, ensure_ascii=False).encode())

            issue_entity = _parse_issue(repo, raw_issue)
            issue_entity.raw_storage_key = raw_key
            repos["issue"].save(issue_entity)
            collected += 1
        except Exception:
            logger.exception("Failed to collect Issue #%s for %s", raw_issue.get("number"), repo.full_name)

    logger.info("Collected %d issues for %s", collected, repo.full_name)
    return collected


def _parse_issue(repo: GitHubRepo, raw: dict) -> GitHubIssue:
    body = raw.get("body") or ""
    linked_prs = _extract_linked_prs(body)

    return GitHubIssue(
        repo_id=repo.id,
        issue_number=raw["number"],
        title=raw.get("title", ""),
        body=raw.get("body"),
        state=raw.get("state", "open"),
        author=raw.get("user", {}).get("login", ""),
        labels=[l["name"] for l in raw.get("labels", [])],
        created_at=_parse_dt(raw.get("created_at")),
        updated_at=_parse_dt(raw.get("updated_at")),
        closed_at=_parse_dt(raw.get("closed_at")),
        linked_pr_numbers=linked_prs if linked_prs else None,
        raw_storage_key=None,
        metadata={
            "html_url": raw.get("html_url"),
            "comments": raw.get("comments", 0),
        },
    )


# ============================================================
# Helpers
# ============================================================

def _build_repositories(database_url: str) -> dict:
    return {
        "repo": GitHubRepoRepository(database_url),
        "pr": GitHubPRRepository(database_url),
        "issue": GitHubIssueRepository(database_url),
        "pr_files": GitHubPRFilesRepository(database_url),
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _extract_linked_prs(body: str) -> list[int]:
    matches = LINKED_PR_PATTERN.findall(body)
    return [int(m) for m in matches] if matches else []
