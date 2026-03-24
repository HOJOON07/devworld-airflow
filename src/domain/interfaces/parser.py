from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class ParsedArticle:
    url: str
    title: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    metadata: dict | None = None


class Parser(Protocol):
    def parse(self, raw_content: str, source_type: str) -> list[ParsedArticle]: ...
