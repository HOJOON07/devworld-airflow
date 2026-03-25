"""
Integration tests for dbt models.

These tests verify that:
- dbt models compile successfully (SQL generation works)
- dbt schema tests can be invoked without configuration errors

Requires dbt-core and dbt-duckdb to be installed.
Uses in-memory DuckDB (dev target) for isolated testing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

DBT_PROJECT_DIR = str(Path(__file__).resolve().parents[2] / "dbt")


def _run_dbt(*args: str, expect_success: bool = True) -> subprocess.CompletedProcess:
    """Run a dbt command against the project directory.

    Uses the dev target (DuckDB in-memory) for isolated testing.
    """
    cmd = [
        "dbt",
        *args,
        "--project-dir", DBT_PROJECT_DIR,
        "--profiles-dir", DBT_PROJECT_DIR,
        "--target", "dev",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "DUCKDB_PATH": ":memory:"},
    )
    if expect_success:
        assert result.returncode == 0, (
            f"dbt {' '.join(args)} failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result


class TestDbtCompile:
    """Verify that dbt models compile without errors."""

    def test_dbt_parse_succeeds(self):
        """dbt should parse the project manifest without errors.

        This validates YAML schema files, model references, and project config
        without actually compiling SQL (no database connection needed).
        """
        _run_dbt("parse")

    def test_dbt_compile_succeeds(self):
        """All models should compile to valid SQL.

        Note: stg_articles reads from S3 via read_parquet, so compilation
        validates Jinja rendering and SQL generation but not data access.
        """
        _run_dbt("compile")


class TestDbtSchemaTests:
    """Verify dbt schema tests can be invoked.

    The bronze model reads from S3 parquet files, so tests will fail at
    runtime without actual data in MinIO/R2. We verify that:
    - Exit code 0: tests pass (data exists and passes constraints)
    - Exit code 1: test failure (expected without data)
    - Exit code 2: compilation/config error (unexpected — fail the test)
    """

    def test_dbt_test_no_config_errors(self):
        """dbt test should not fail with configuration or compilation errors."""
        result = _run_dbt("test", expect_success=False)

        if result.returncode == 0:
            return

        # Exit code 1 = test failure (acceptable: no source data available)
        # Exit code 2 = compilation/config error (should not happen)
        assert result.returncode == 1, (
            f"dbt test had configuration/compilation error (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
