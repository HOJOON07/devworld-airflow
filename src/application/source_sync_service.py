"""Source Sync Service — syncs config/sources.yml to crawl_sources DB table."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.infrastructure.repository.postgres_repository import (
    PostgresCrawlSourceRepository,
)
from src.domain.entities.crawl_source import CrawlSource
from src.shared.logging import setup_logging

logger = setup_logging(__name__)

DEFAULT_SOURCES_PATH = "/opt/airflow/config/sources.yml"


def sync_sources(database_url: str, sources_path: str = DEFAULT_SOURCES_PATH) -> dict:
    """Sync sources.yml to crawl_sources table.

    - New sources in YAML → INSERT into DB
    - Existing sources → UPDATE (feed_url, source_type, is_active, etc.)
    - Sources in DB but not in YAML → SET is_active = false

    Returns summary dict with added/updated/deactivated counts.
    """
    path = Path(sources_path)
    if not path.exists():
        raise FileNotFoundError(f"Sources file not found: {sources_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    yml_sources = config.get("sources", [])
    if not yml_sources:
        logger.warning("No sources found in %s", sources_path)
        return {"added": 0, "updated": 0, "deactivated": 0}

    repo = PostgresCrawlSourceRepository(database_url)
    existing = {s.name: s for s in repo.find_all()}
    yml_names = set()

    added = 0
    updated = 0

    for src in yml_sources:
        name = src["name"]
        yml_names.add(name)

        if name in existing:
            # Update existing source
            db_source = existing[name]
            db_source.source_type = src.get("source_type", db_source.source_type)
            db_source.base_url = src.get("base_url", db_source.base_url)
            db_source.feed_url = src.get("feed_url", db_source.feed_url)
            db_source.is_active = src.get("is_active", db_source.is_active)
            db_source.crawl_config = src.get("crawl_config")
            repo.save(db_source)
            updated += 1
            logger.info("Updated source: %s", name)
        else:
            # Insert new source
            new_source = CrawlSource(
                name=name,
                source_type=src.get("source_type", "rss"),
                base_url=src["base_url"],
                feed_url=src.get("feed_url"),
                is_active=src.get("is_active", True),
                crawl_config=src.get("crawl_config"),
            )
            repo.save(new_source)
            added += 1
            logger.info("Added new source: %s", name)

    # Deactivate sources not in YAML
    deactivated = 0
    for name, db_source in existing.items():
        if name not in yml_names and db_source.is_active:
            db_source.is_active = False
            repo.save(db_source)
            deactivated += 1
            logger.info("Deactivated source not in YAML: %s", name)

    summary = {"added": added, "updated": updated, "deactivated": deactivated}
    logger.info("Source sync complete: %s", summary)
    return summary
