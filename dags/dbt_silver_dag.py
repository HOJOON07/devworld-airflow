"""dbt Silver DAG — transforms Bronze to Silver.

Triggered by bronze_ready asset (after dlt_load).
Produces silver_ready asset to trigger ai_enrich.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig, RenderConfig
from cosmos.profiles.postgres import PostgresUserPasswordProfileMapping

from assets import bronze_ready, silver_ready


@dag(
    dag_id="dbt_silver",
    schedule=bronze_ready,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "transform", "silver"],
)
def dbt_silver():
    dbt_group = DbtTaskGroup(
        group_id="silver_transform",
        project_config=ProjectConfig(
            dbt_project_path="/opt/airflow/dbt",
        ),
        render_config=RenderConfig(
            select=["path:models/bronze", "path:models/silver"],
        ),
        profile_config=ProfileConfig(
            profile_name="devworld",
            target_name="dev",
            profile_mapping=PostgresUserPasswordProfileMapping(
                conn_id="postgres_app",
                profile_args={"schema": "public"},
            ),
        ),
        execution_config=ExecutionConfig(
            dbt_executable_path="/home/airflow/.local/bin/dbt",
        ),
        operator_args={"install_deps": True},
    )

    @task(outlets=[silver_ready])
    def mark_silver_ready():
        from src.shared.logging import setup_logging
        logger = setup_logging("dbt_silver")
        logger.info("Silver transform complete")

    dbt_group >> mark_silver_ready()


dbt_silver()
