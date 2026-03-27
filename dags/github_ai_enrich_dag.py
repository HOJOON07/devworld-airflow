"""GitHub AI Enrich DAG — enriches collected GitHub PRs and issues with AI.

Triggered by github_collected asset (after github_collect).
Produces github_enriched asset to trigger github_dbt_gold.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task

from assets import github_collected, github_enriched


@dag(
    dag_id="github_ai_enrich",
    schedule=github_collected,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["github", "ai", "enrich"],
)
def github_ai_enrich():
    @task(outlets=[github_enriched])
    def enrich() -> dict:
        """Enrich GitHub PRs and issues with AI-generated summaries."""
        from src.application.github_enrich_service import (
            enrich_github_issues,
            enrich_github_prs,
        )
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("github_ai_enrich")
        config = Config()

        logger.info("[enrich] Starting GitHub AI enrichment...")
        pr_count = enrich_github_prs(config)
        issue_count = enrich_github_issues(config)
        logger.info("[enrich] Done. %d PRs, %d issues enriched", pr_count, issue_count)

        return {"prs_enriched": pr_count, "issues_enriched": issue_count}

    enrich()


github_ai_enrich()
