from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CrawlJob:
    source_id: str
    partition_date: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    discovered_count: int = 0
    fetched_count: int = 0
    parsed_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
