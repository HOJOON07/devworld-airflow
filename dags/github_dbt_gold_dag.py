"""GitHub dbt Gold DAG — builds GitHub Gold mart and syncs to serving.

Triggered by github_enriched asset (after github_ai_enrich).
Produces github_gold_ready asset.
Includes reverse_etl to sync Gold results to PostgreSQL serving tables.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, task
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig, RenderConfig

from assets import github_enriched, github_gold_ready
from common import DEFAULT_ARGS

DBT_PROJECT_PATH = "/opt/airflow/dbt"


@dag(
    dag_id="github_dbt_gold",
    default_args=DEFAULT_ARGS,
    schedule=github_enriched,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["github", "dbt", "gold", "serving"],
)
def github_dbt_gold():
    profile_config = ProfileConfig(
        profile_name="devworld",
        target_name="dev",
        profiles_yml_filepath=Path(DBT_PROJECT_PATH) / "profiles.yml",
    )
    project_config = ProjectConfig(
        dbt_project_path=DBT_PROJECT_PATH,
    )
    execution_config = ExecutionConfig(
        dbt_executable_path="/home/airflow/.local/bin/dbt",
    )

    github_gold_transform = DbtTaskGroup(
        group_id="github_gold_transform",
        project_config=project_config,
        render_config=RenderConfig(
            select=["path:models/github_gold"],
        ),
        profile_config=profile_config,
        execution_config=execution_config,
        operator_args={"install_deps": True},
    )

    github_reverse_etl = DbtTaskGroup(
        group_id="github_reverse_etl",
        project_config=project_config,
        render_config=RenderConfig(
            select=["serving_github_prs", "serving_github_issues"],
        ),
        profile_config=profile_config,
        execution_config=execution_config,
        operator_args={"install_deps": True},
    )

    @task()
    def create_github_fts_index():
        """PostgreSQL serving_github_prs에 tsvector + GIN 생성."""
        from sqlalchemy import create_engine, text
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("github_dbt_gold.fts")
        config = Config()
        engine = create_engine(config.database.url, pool_pre_ping=True)

        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE serving.serving_github_prs "
                "ADD COLUMN IF NOT EXISTS search_vector tsvector"
            ))
            conn.execute(text(
                "UPDATE serving.serving_github_prs SET search_vector = "
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(repo_name, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(ai_summary, '')), 'C')"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS serving_github_prs_search_idx "
                "ON serving.serving_github_prs USING GIN (search_vector)"
            ))
            conn.commit()

        logger.info("FTS index created on serving.serving_github_prs")

    @task(outlets=[github_gold_ready])
    def mark_github_gold_ready():
        from src.shared.logging import setup_logging
        logger = setup_logging("github_dbt_gold")
        logger.info("GitHub Gold transform + reverse ETL + FTS complete")

    github_gold_transform >> github_reverse_etl >> create_github_fts_index() >> mark_github_gold_ready()


github_dbt_gold()
