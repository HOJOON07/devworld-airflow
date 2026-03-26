"""AI Enrich DAG — extracts keywords, topics, summary from articles.

Triggered by silver_ready asset (after dbt_silver).
Produces enrichments_ready asset to trigger dbt_gold.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task

from assets import silver_ready, enrichments_ready


@dag(
    dag_id="ai_enrich",
    schedule=silver_ready,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ai", "enrich", "keywords", "topics"],
)
def ai_enrich():
    @task(outlets=[enrichments_ready])
    def enrich() -> dict:
        """Enrich Silver articles with AI-generated keywords and topics."""
        from src.application.enrich_service import enrich_articles
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("ai_enrich")
        config = Config()

        logger.info("[enrich] Starting AI enrichment...")
        count = enrich_articles(config)
        logger.info("[enrich] Done. %d articles enriched", count)

        return {"enriched": count}

    enrich()


ai_enrich()
