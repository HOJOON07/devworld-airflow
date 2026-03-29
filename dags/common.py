"""Common DAG configuration shared by all DAGs."""

from __future__ import annotations

from datetime import timedelta

from src.shared.logging import setup_logging

logger = setup_logging("dag_common")


def on_failure(context: dict) -> None:
    """DAG task failure callback. Logs failure details."""
    task_instance = context.get("task_instance")
    dag_id = task_instance.dag_id if task_instance else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    exception = context.get("exception", "")
    logger.error(
        "Task failed: dag=%s task=%s error=%s",
        dag_id,
        task_id,
        str(exception)[:500],
    )


DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
    "on_failure_callback": on_failure,
}
