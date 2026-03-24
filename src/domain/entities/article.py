from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    source_id: str
    url: str
    discovered_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    raw_storage_key: str | None = None
    content_hash: str | None = None
    metadata: dict | None = None
