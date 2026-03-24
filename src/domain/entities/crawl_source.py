from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CrawlSource:
    name: str
    source_type: str
    base_url: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    feed_url: str | None = None
    crawl_config: dict | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
