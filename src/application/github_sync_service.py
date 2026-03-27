"""GitHub Sync Service — syncs config/github_repos.yml to github_repos DB table."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.domain.entities.github_repo import GitHubRepo
from src.infrastructure.github.github_repository import GitHubRepoRepository
from src.shared.logging import setup_logging

logger = setup_logging(__name__)

DEFAULT_GITHUB_REPOS_PATH = "/opt/airflow/config/github_repos.yml"


def sync_github_repos(
    database_url: str,
    repos_path: str = DEFAULT_GITHUB_REPOS_PATH,
) -> dict:
    """Sync github_repos.yml to github_repos table.

    - New repos in YAML -> INSERT into DB
    - Existing repos -> UPDATE (owner, name)
    - Repos in DB but not in YAML -> no action (keep historical data)

    Returns summary dict with added/updated counts.
    """
    path = Path(repos_path)
    if not path.exists():
        raise FileNotFoundError(f"GitHub repos file not found: {repos_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    yml_repos = config.get("repos", [])
    if not yml_repos:
        logger.warning("No repos found in %s", repos_path)
        return {"added": 0, "updated": 0}

    repo_repository = GitHubRepoRepository(database_url)
    existing = {r.full_name: r for r in repo_repository.find_all()}

    added = 0
    updated = 0

    for entry in yml_repos:
        owner = entry["owner"]
        name = entry["name"]
        full_name = f"{owner}/{name}"

        if full_name in existing:
            db_repo = existing[full_name]
            db_repo.owner = owner
            db_repo.name = name
            repo_repository.save(db_repo)
            updated += 1
            logger.info("Updated GitHub repo: %s", full_name)
        else:
            new_repo = GitHubRepo(
                owner=owner,
                name=name,
                full_name=full_name,
            )
            repo_repository.save(new_repo)
            added += 1
            logger.info("Added new GitHub repo: %s", full_name)

    summary = {"added": added, "updated": updated}
    logger.info("GitHub repo sync complete: %s", summary)
    return summary
