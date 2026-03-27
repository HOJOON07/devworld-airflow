from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GitHubPR:
    repo_id: str
    pr_number: int
    title: str
    body: str | None
    state: str  # open/closed/merged
    author: str
    labels: list | None
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None
    diff_text: str | None  # top 10 files patch combined
    raw_storage_key: str | None
    metadata: dict | None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
