"""Enrich Service -- AI enrichment for articles (keywords, topics, summary)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from src.infrastructure.ai.ollama_client import extract_keywords_and_topics
from src.infrastructure.ducklake import create_ducklake_connection
from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def enrich_articles(config: Config) -> int:
    """Enrich Silver articles that haven't been enriched yet.

    Reads from DuckLake Silver (int_articles_cleaned), calls Ollama API,
    stores results in PostgreSQL article_enrichments table.

    Returns number of articles enriched.
    """
    # Read candidate articles from DuckLake Silver
    duck_conn = create_ducklake_connection(config)
    rows = duck_conn.execute("""
        SELECT id, title, content_text
        FROM devworld_lake.silver.int_articles_cleaned
        WHERE content_text IS NOT NULL
        ORDER BY published_at DESC NULLS LAST
    """).fetchall()
    duck_conn.close()

    if not rows:
        logger.info("No articles in Silver")
        return 0

    # Check which articles are already enriched via PostgreSQL
    engine = create_engine(config.database.url, pool_pre_ping=True)
    with engine.connect() as pg_conn:
        enriched_ids = {
            str(r[0])
            for r in pg_conn.execute(
                text("SELECT article_id FROM article_enrichments")
            ).fetchall()
        }

    # Filter out already enriched
    rows = [(id_, title, content) for id_, title, content in rows if str(id_) not in enriched_ids]

    if not rows:
        logger.info("All articles already enriched")
        return 0

    logger.info("Enriching %d articles", len(rows))
    enriched_count = 0

    for id_, title, content_text in rows:
        result = extract_keywords_and_topics(
            title=title or "",
            content_text=content_text or "",
        )

        if not result["keywords"] and not result["topics"]:
            logger.warning("Empty enrichment for article id=%s", id_)
            continue

        with engine.connect() as pg_conn:
            pg_conn.execute(
                text("""
                    INSERT INTO article_enrichments (article_id, keywords, topics, summary, enriched_at)
                    VALUES (:article_id, :keywords, :topics, :summary, :enriched_at)
                    ON CONFLICT (article_id) DO UPDATE SET
                        keywords = EXCLUDED.keywords,
                        topics = EXCLUDED.topics,
                        summary = EXCLUDED.summary,
                        enriched_at = EXCLUDED.enriched_at
                """),
                {
                    "article_id": str(id_),
                    "keywords": json.dumps(result["keywords"], ensure_ascii=False),
                    "topics": json.dumps(result["topics"], ensure_ascii=False),
                    "summary": result["summary"],
                    "enriched_at": datetime.now(timezone.utc),
                },
            )
            pg_conn.commit()

        enriched_count += 1

    logger.info("Enriched %d/%d articles", enriched_count, len(rows))
    return enriched_count
