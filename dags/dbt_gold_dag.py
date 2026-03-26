"""dbt Gold DAG — builds Gold mart from Silver + AI enrichments.

Triggered by enrichments_ready asset (after ai_enrich).
Produces gold_ready asset. Final step of the pipeline.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig, RenderConfig
from cosmos.profiles.postgres import PostgresUserPasswordProfileMapping

from assets import enrichments_ready, gold_ready


@dag(
    dag_id="dbt_gold",
    schedule=enrichments_ready,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "gold", "serving"],
)
def dbt_gold():
    dbt_group = DbtTaskGroup(
        group_id="gold_transform",
        project_config=ProjectConfig(
            dbt_project_path="/opt/airflow/dbt",
        ),
        render_config=RenderConfig(
            select=["path:models/gold"],
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

    @task(outlets=[gold_ready])
    def mark_gold_ready():
        from src.shared.logging import setup_logging
        logger = setup_logging("dbt_gold")
        logger.info("Gold transform complete")

    dbt_group >> mark_gold_ready()


dbt_gold()
