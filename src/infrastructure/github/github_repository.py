from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.domain.entities.github_issue import GitHubIssue
from src.domain.entities.github_pr import GitHubPR
from src.domain.entities.github_repo import GitHubRepo
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def _build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# GitHubRepoRepository
# ---------------------------------------------------------------------------

class GitHubRepoRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, repo: GitHubRepo) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO github_repos (
                        id, owner, name, full_name,
                        last_collected_at, created_at
                    ) VALUES (
                        :id, :owner, :name, :full_name,
                        :last_collected_at, :created_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        owner = EXCLUDED.owner,
                        name = EXCLUDED.name,
                        full_name = EXCLUDED.full_name,
                        last_collected_at = EXCLUDED.last_collected_at
                    """
                ),
                {
                    "id": repo.id,
                    "owner": repo.owner,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "last_collected_at": repo.last_collected_at,
                    "created_at": repo.created_at,
                },
            )
            conn.commit()

    def find_by_full_name(self, full_name: str) -> GitHubRepo | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM github_repos WHERE full_name = :full_name"),
                {"full_name": full_name},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_repo(row)

    def find_all(self) -> list[GitHubRepo]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM github_repos")
            ).mappings().all()
        return [self._row_to_repo(row) for row in rows]

    def update_last_collected(self, repo_id: str, collected_at: datetime) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE github_repos
                    SET last_collected_at = :collected_at
                    WHERE id = :id
                    """
                ),
                {"id": repo_id, "collected_at": collected_at},
            )
            conn.commit()

    @staticmethod
    def _row_to_repo(row: dict) -> GitHubRepo:
        return GitHubRepo(
            id=row["id"],
            owner=row["owner"],
            name=row["name"],
            full_name=row["full_name"],
            last_collected_at=row["last_collected_at"],
            created_at=row["created_at"],
        )


# ---------------------------------------------------------------------------
# GitHubPRRepository
# ---------------------------------------------------------------------------

class GitHubPRRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, pr: GitHubPR) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO github_prs (
                        id, repo_id, pr_number, title, body, state,
                        author, labels, created_at, updated_at,
                        merged_at, diff_text, raw_storage_key, metadata
                    ) VALUES (
                        :id, :repo_id, :pr_number, :title, :body, :state,
                        :author, :labels, :created_at, :updated_at,
                        :merged_at, :diff_text, :raw_storage_key, :metadata
                    )
                    ON CONFLICT (repo_id, pr_number) DO UPDATE SET
                        title = EXCLUDED.title,
                        body = EXCLUDED.body,
                        state = EXCLUDED.state,
                        author = EXCLUDED.author,
                        labels = EXCLUDED.labels,
                        updated_at = EXCLUDED.updated_at,
                        merged_at = EXCLUDED.merged_at,
                        diff_text = EXCLUDED.diff_text,
                        raw_storage_key = EXCLUDED.raw_storage_key,
                        metadata = EXCLUDED.metadata
                    """
                ),
                {
                    "id": pr.id,
                    "repo_id": pr.repo_id,
                    "pr_number": pr.pr_number,
                    "title": pr.title,
                    "body": pr.body,
                    "state": pr.state,
                    "author": pr.author,
                    "labels": json.dumps(pr.labels) if pr.labels else None,
                    "created_at": pr.created_at,
                    "updated_at": pr.updated_at,
                    "merged_at": pr.merged_at,
                    "diff_text": pr.diff_text,
                    "raw_storage_key": pr.raw_storage_key,
                    "metadata": json.dumps(pr.metadata) if pr.metadata else None,
                },
            )
            conn.commit()

    def find_by_repo_and_number(
        self, repo_id: str, pr_number: int
    ) -> GitHubPR | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM github_prs
                    WHERE repo_id = :repo_id AND pr_number = :pr_number
                    """
                ),
                {"repo_id": repo_id, "pr_number": pr_number},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_pr(row)

    def exists_by_repo_and_number(self, repo_id: str, pr_number: int) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT 1 FROM github_prs
                    WHERE repo_id = :repo_id AND pr_number = :pr_number
                    LIMIT 1
                    """
                ),
                {"repo_id": repo_id, "pr_number": pr_number},
            ).first()
        return result is not None

    @staticmethod
    def _row_to_pr(row: dict) -> GitHubPR:
        labels = row["labels"]
        if isinstance(labels, str):
            labels = json.loads(labels)
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return GitHubPR(
            id=row["id"],
            repo_id=row["repo_id"],
            pr_number=row["pr_number"],
            title=row["title"],
            body=row["body"],
            state=row["state"],
            author=row["author"],
            labels=labels,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            merged_at=row["merged_at"],
            diff_text=row["diff_text"],
            raw_storage_key=row["raw_storage_key"],
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# GitHubIssueRepository
# ---------------------------------------------------------------------------

class GitHubIssueRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save(self, issue: GitHubIssue) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO github_issues (
                        id, repo_id, issue_number, title, body, state,
                        author, labels, created_at, updated_at,
                        closed_at, linked_pr_numbers, raw_storage_key, metadata
                    ) VALUES (
                        :id, :repo_id, :issue_number, :title, :body, :state,
                        :author, :labels, :created_at, :updated_at,
                        :closed_at, :linked_pr_numbers, :raw_storage_key, :metadata
                    )
                    ON CONFLICT (repo_id, issue_number) DO UPDATE SET
                        title = EXCLUDED.title,
                        body = EXCLUDED.body,
                        state = EXCLUDED.state,
                        author = EXCLUDED.author,
                        labels = EXCLUDED.labels,
                        updated_at = EXCLUDED.updated_at,
                        closed_at = EXCLUDED.closed_at,
                        linked_pr_numbers = EXCLUDED.linked_pr_numbers,
                        raw_storage_key = EXCLUDED.raw_storage_key,
                        metadata = EXCLUDED.metadata
                    """
                ),
                {
                    "id": issue.id,
                    "repo_id": issue.repo_id,
                    "issue_number": issue.issue_number,
                    "title": issue.title,
                    "body": issue.body,
                    "state": issue.state,
                    "author": issue.author,
                    "labels": json.dumps(issue.labels) if issue.labels else None,
                    "created_at": issue.created_at,
                    "updated_at": issue.updated_at,
                    "closed_at": issue.closed_at,
                    "linked_pr_numbers": (
                        json.dumps(issue.linked_pr_numbers)
                        if issue.linked_pr_numbers
                        else None
                    ),
                    "raw_storage_key": issue.raw_storage_key,
                    "metadata": json.dumps(issue.metadata) if issue.metadata else None,
                },
            )
            conn.commit()

    def find_by_repo_and_number(
        self, repo_id: str, issue_number: int
    ) -> GitHubIssue | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM github_issues
                    WHERE repo_id = :repo_id AND issue_number = :issue_number
                    """
                ),
                {"repo_id": repo_id, "issue_number": issue_number},
            ).mappings().first()
        if not row:
            return None
        return self._row_to_issue(row)

    def exists_by_repo_and_number(self, repo_id: str, issue_number: int) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT 1 FROM github_issues
                    WHERE repo_id = :repo_id AND issue_number = :issue_number
                    LIMIT 1
                    """
                ),
                {"repo_id": repo_id, "issue_number": issue_number},
            ).first()
        return result is not None

    @staticmethod
    def _row_to_issue(row: dict) -> GitHubIssue:
        labels = row["labels"]
        if isinstance(labels, str):
            labels = json.loads(labels)
        linked_pr_numbers = row["linked_pr_numbers"]
        if isinstance(linked_pr_numbers, str):
            linked_pr_numbers = json.loads(linked_pr_numbers)
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return GitHubIssue(
            id=row["id"],
            repo_id=row["repo_id"],
            issue_number=row["issue_number"],
            title=row["title"],
            body=row["body"],
            state=row["state"],
            author=row["author"],
            labels=labels,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
            linked_pr_numbers=linked_pr_numbers,
            raw_storage_key=row["raw_storage_key"],
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# GitHubPRFilesRepository
# ---------------------------------------------------------------------------

class GitHubPRFilesRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = _build_engine(database_url)

    def save_batch(self, pr_id: str, files: list[dict]) -> None:
        if not files:
            return
        with self._engine.connect() as conn:
            # Delete existing files for this PR before re-inserting
            conn.execute(
                text("DELETE FROM github_pr_files WHERE pr_id = :pr_id"),
                {"pr_id": pr_id},
            )
            for f in files:
                conn.execute(
                    text(
                        """
                        INSERT INTO github_pr_files (
                            pr_id, filename, status, additions,
                            deletions, changes, patch
                        ) VALUES (
                            :pr_id, :filename, :status, :additions,
                            :deletions, :changes, :patch
                        )
                        """
                    ),
                    {
                        "pr_id": pr_id,
                        "filename": f.get("filename"),
                        "status": f.get("status"),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "changes": f.get("changes", 0),
                        "patch": f.get("patch"),
                    },
                )
            conn.commit()
