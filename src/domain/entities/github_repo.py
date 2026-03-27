from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GitHubRepo:
    owner: str
    name: str
    full_name: str  # "facebook/react"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_collected_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
