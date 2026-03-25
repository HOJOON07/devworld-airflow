"""dbt Transform DAG — transforms Bronze to Silver to Gold.

Uses Astronomer Cosmos to render dbt models as individual Airflow tasks.
Each dbt model gets its own task — model-level observability and retry.

Runs daily at KST 02:00 (UTC 17:00), after dlt_load.
"""

from datetime import datetime

from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig
from cosmos.profiles.postgres import PostgresUserPasswordProfileMapping

dbt_transform = DbtDag(
    dag_id="dbt_transform",
    schedule="0 17 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "transform", "silver", "gold"],
    project_config=ProjectConfig(
        dbt_project_path="/opt/airflow/dbt",
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
