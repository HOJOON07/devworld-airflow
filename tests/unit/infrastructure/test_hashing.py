"""Unit tests for content hashing utility."""

from __future__ import annotations

import pytest

from src.shared.hashing import compute_content_hash

pytestmark = pytest.mark.unit


class TestComputeContentHash:
    def test_deterministic(self):
        """Same input must always produce the same hash."""
        content = "Hello, world!"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_different_input_different_hash(self):
        """Different inputs must produce different hashes."""
        h1 = compute_content_hash("content A")
        h2 = compute_content_hash("content B")
        assert h1 != h2

    def test_returns_hex_string(self):
        """Hash should be a valid hexadecimal string."""
        result = compute_content_hash("test")
        assert isinstance(result, str)
        # SHA-256 produces 64 hex chars
        assert len(result) == 64
        int(result, 16)  # should not raise

    def test_empty_string(self):
        """Empty string should still produce a valid hash."""
        result = compute_content_hash("")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_unicode_content(self):
        """Unicode content should be handled correctly."""
        h1 = compute_content_hash("한글 테스트")
        h2 = compute_content_hash("한글 테스트")
        assert h1 == h2

    def test_whitespace_sensitivity(self):
        """Trailing/leading whitespace differences produce different hashes."""
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("hello ")
        assert h1 != h2
