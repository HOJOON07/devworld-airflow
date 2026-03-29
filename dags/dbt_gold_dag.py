"""dbt Gold DAG -- builds Gold mart from Silver + AI enrichments.

Triggered by enrichments_ready asset (after ai_enrich).
Produces gold_ready asset. Final step of the pipeline.
Includes reverse_etl to sync Gold results back to PostgreSQL serving tables.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, task
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig, RenderConfig

from assets import enrichments_ready, gold_ready
from common import DEFAULT_ARGS

DBT_PROJECT_PATH = "/opt/airflow/dbt"


@dag(
    dag_id="dbt_gold",
    default_args=DEFAULT_ARGS,
    schedule=enrichments_ready,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "gold", "serving"],
)
def dbt_gold():
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

    gold_transform = DbtTaskGroup(
        group_id="gold_transform",
        project_config=project_config,
        render_config=RenderConfig(
            select=["path:models/gold"],
        ),
        profile_config=profile_config,
        execution_config=execution_config,
        operator_args={"install_deps": True},
    )

    reverse_etl = DbtTaskGroup(
        group_id="reverse_etl",
        project_config=project_config,
        render_config=RenderConfig(
            select=["serving_articles", "serving_trending_topics", "serving_keyword_stats", "serving_source_stats"],
        ),
        profile_config=profile_config,
        execution_config=execution_config,
        operator_args={"install_deps": True},
    )

    @task()
    def create_fts_index():
        """PostgreSQL serving_articles에 tsvector + GIN 인덱스 생성.

        dbt-duckdb는 DuckDB를 통해 SQL을 실행하므로
        PostgreSQL 전용 DDL(tsvector, GIN)을 post_hook으로 실행할 수 없다.
        이 task에서 PostgreSQL에 직접 연결하여 FTS를 생성한다.
        """
        from sqlalchemy import create_engine, text
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("dbt_gold.fts")
        config = Config()
        engine = create_engine(config.database.url, pool_pre_ping=True)

        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE serving.serving_articles "
                "ADD COLUMN IF NOT EXISTS search_vector tsvector"
            ))
            conn.execute(text(
                "UPDATE serving.serving_articles SET search_vector = "
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(source_name, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(content_text, '')), 'C')"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS serving_articles_search_idx "
                "ON serving.serving_articles USING GIN (search_vector)"
            ))
            conn.commit()

        logger.info("FTS index created on serving.serving_articles")

    @task(outlets=[gold_ready])
    def mark_gold_ready():
        from src.shared.logging import setup_logging
        logger = setup_logging("dbt_gold")
        logger.info("Gold transform + reverse ETL + FTS complete")

    gold_transform >> reverse_etl >> create_fts_index() >> mark_gold_ready()


dbt_gold()
