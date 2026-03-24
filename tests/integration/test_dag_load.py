"""
Integration test: verify all DAGs load without import errors.

This test uses Airflow's DagBag to import every DAG file under dags/
and asserts that no import errors occurred and each DAG has at least one task.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

DAGS_DIR = str(Path(__file__).resolve().parents[2] / "dags")


@pytest.fixture(scope="module")
def dagbag():
    """Load all DAGs from the project dags/ directory."""
    os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
    from airflow.models import DagBag

    bag = DagBag(dag_folder=DAGS_DIR, include_examples=False)
    return bag


def test_no_import_errors(dagbag):
    """Every DAG file should parse without import errors."""
    assert dagbag.import_errors == {}, (
        f"DAG import errors found:\n"
        + "\n".join(f"  {path}: {err}" for path, err in dagbag.import_errors.items())
    )


def test_dags_have_tasks(dagbag):
    """Each loaded DAG should contain at least one task."""
    assert len(dagbag.dags) > 0, "No DAGs found in dags/ directory"
    for dag_id, dag in dagbag.dags.items():
        assert len(dag.tasks) > 0, f"DAG '{dag_id}' has no tasks"
