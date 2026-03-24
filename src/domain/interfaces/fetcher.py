from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: str
    content_type: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...
