from __future__ import annotations

from typing import Protocol


class StorageAdapter(Protocol):
    def put_object(self, bucket: str, key: str, data: bytes) -> None: ...

    def get_object(self, bucket: str, key: str) -> bytes: ...

    def list_objects(self, bucket: str, prefix: str) -> list[str]: ...
