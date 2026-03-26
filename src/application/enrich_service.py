"""Enrich Service — AI enrichment for articles (keywords, topics, summary)."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine, text

from src.infrastructure.ai.ollama_client import extract_keywords_and_topics
from src.shared.config import Config
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


def enrich_articles(config: Config) -> int:
    """Enrich Silver articles that haven't been enriched yet.

    Reads from int_articles_cleaned (Silver), calls Ollama API,
    stores results in article_enrichments table.

    Returns number of articles enriched.
    """
    engine = create_engine(config.database.url, pool_pre_ping=True)

    # Silver에서 아직 enrichment 안 된 아티클 조회
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT s.id, s.title, s.content_text
                FROM public_public.int_articles_cleaned s
                LEFT JOIN article_enrichments e ON s.id = e.article_id
                WHERE e.article_id IS NULL
                  AND s.content_text IS NOT NULL
                ORDER BY s.published_at DESC NULLS LAST
            """)
        ).mappings().all()

    if not rows:
        logger.info("No articles to enrich")
        return 0

    logger.info("Enriching %d articles", len(rows))
    enriched_count = 0

    for row in rows:
        result = extract_keywords_and_topics(
            title=row["title"] or "",
            content_text=row["content_text"] or "",
        )

        if not result["keywords"] and not result["topics"]:
            logger.warning("Empty enrichment for article id=%s", row["id"])
            continue

        with engine.connect() as conn:
            conn.execute(
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
                    "article_id": str(row["id"]),
                    "keywords": json.dumps(result["keywords"], ensure_ascii=False),
                    "topics": json.dumps(result["topics"], ensure_ascii=False),
                    "summary": result["summary"],
                    "enriched_at": datetime.utcnow(),
                },
            )
            conn.commit()

        enriched_count += 1

    logger.info("Enriched %d/%d articles", enriched_count, len(rows))
    return enriched_count
