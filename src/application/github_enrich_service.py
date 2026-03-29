"""GitHub Enrich Service — AI enrichment for PRs and Issues."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from src.infrastructure.ai.ollama_client import summarize_issue, summarize_pr
from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def enrich_github_prs(config: Config) -> int:
    """Enrich GitHub PRs that haven't been summarized yet.

    Reads from github_prs, calls Ollama API,
    stores results in github_pr_ai_summaries table.

    Returns number of PRs enriched.
    """
    engine = create_engine(config.database.url, pool_pre_ping=True)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT p.id, p.title, p.body, p.diff_text
                FROM github_prs p
                LEFT JOIN github_pr_ai_summaries s ON p.id = s.pr_id
                WHERE s.pr_id IS NULL
                  AND (p.body IS NOT NULL OR p.diff_text IS NOT NULL)
                ORDER BY p.created_at DESC
            """)
        ).mappings().all()

    if not rows:
        logger.info("No PRs to enrich")
        return 0

    logger.info("Enriching %d PRs", len(rows))
    enriched_count = 0

    for row in rows:
        result = summarize_pr(
            title=row["title"] or "",
            body=row["body"] or "",
            diff_text=row["diff_text"] or "",
        )

        if not result["ai_summary"]:
            logger.warning("Empty enrichment for PR id=%s", row["id"])
            continue

        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO github_pr_ai_summaries
                        (pr_id, ai_summary, key_changes, impact_analysis,
                         change_type, ai_code_review, keywords, enriched_at)
                    VALUES
                        (:pr_id, :ai_summary, :key_changes, :impact_analysis,
                         :change_type, :ai_code_review, :keywords, :enriched_at)
                    ON CONFLICT (pr_id) DO UPDATE SET
                        ai_summary = EXCLUDED.ai_summary,
                        key_changes = EXCLUDED.key_changes,
                        impact_analysis = EXCLUDED.impact_analysis,
                        change_type = EXCLUDED.change_type,
                        ai_code_review = EXCLUDED.ai_code_review,
                        keywords = EXCLUDED.keywords,
                        enriched_at = EXCLUDED.enriched_at
                """),
                {
                    "pr_id": str(row["id"]),
                    "ai_summary": result["ai_summary"],
                    "key_changes": json.dumps(result["key_changes"], ensure_ascii=False),
                    "impact_analysis": result["impact_analysis"],
                    "change_type": result["change_type"],
                    "ai_code_review": result["ai_code_review"],
                    "keywords": json.dumps(result["keywords"], ensure_ascii=False),
                    "enriched_at": datetime.now(timezone.utc),
                },
            )
            conn.commit()

        enriched_count += 1

    logger.info("Enriched %d/%d PRs", enriched_count, len(rows))
    return enriched_count


def enrich_github_issues(config: Config) -> int:
    """Enrich GitHub Issues that haven't been summarized yet.

    Reads from github_issues, calls Ollama API,
    stores results in github_issue_ai_summaries table.

    Returns number of Issues enriched.
    """
    engine = create_engine(config.database.url, pool_pre_ping=True)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT i.id, i.title, i.body
                FROM github_issues i
                LEFT JOIN github_issue_ai_summaries s ON i.id = s.issue_id
                WHERE s.issue_id IS NULL
                  AND i.body IS NOT NULL
                ORDER BY i.created_at DESC
            """)
        ).mappings().all()

    if not rows:
        logger.info("No Issues to enrich")
        return 0

    logger.info("Enriching %d Issues", len(rows))
    enriched_count = 0

    for row in rows:
        result = summarize_issue(
            title=row["title"] or "",
            body=row["body"] or "",
        )

        if not result["ai_summary"]:
            logger.warning("Empty enrichment for Issue id=%s", row["id"])
            continue

        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO github_issue_ai_summaries
                        (issue_id, ai_summary, key_points, suggested_solution,
                         contribution_difficulty, keywords, enriched_at)
                    VALUES
                        (:issue_id, :ai_summary, :key_points, :suggested_solution,
                         :contribution_difficulty, :keywords, :enriched_at)
                    ON CONFLICT (issue_id) DO UPDATE SET
                        ai_summary = EXCLUDED.ai_summary,
                        key_points = EXCLUDED.key_points,
                        suggested_solution = EXCLUDED.suggested_solution,
                        contribution_difficulty = EXCLUDED.contribution_difficulty,
                        keywords = EXCLUDED.keywords,
                        enriched_at = EXCLUDED.enriched_at
                """),
                {
                    "issue_id": str(row["id"]),
                    "ai_summary": result["ai_summary"],
                    "key_points": json.dumps(result["key_points"], ensure_ascii=False),
                    "suggested_solution": result["suggested_solution"],
                    "contribution_difficulty": result["contribution_difficulty"],
                    "keywords": json.dumps(result["keywords"], ensure_ascii=False),
                    "enriched_at": datetime.now(timezone.utc),
                },
            )
            conn.commit()

        enriched_count += 1

    logger.info("Enriched %d/%d Issues", enriched_count, len(rows))
    return enriched_count
