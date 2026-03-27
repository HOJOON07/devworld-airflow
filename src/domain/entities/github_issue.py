from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GitHubIssue:
    repo_id: str
    issue_number: int
    title: str
    body: str | None
    state: str  # open/closed
    author: str
    labels: list | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    linked_pr_numbers: list | None
    raw_storage_key: str | None
    metadata: dict | None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
