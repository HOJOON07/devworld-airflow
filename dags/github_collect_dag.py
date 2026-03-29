"""GitHub Collect DAG — collects PRs and issues from tracked repositories.

Runs daily at KST 06:00 (UTC 21:00).
Produces github_collected asset to trigger github_ai_enrich.
"""

from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag, task

from assets import github_collected
from common import DEFAULT_ARGS


@dag(
    dag_id="github_collect",
    default_args=DEFAULT_ARGS,
    schedule="0 21 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["github", "collect"],
)
def github_collect():
    @task()
    def sync_repos() -> dict:
        """Sync config/github_repos.yml to github repos DB table."""
        from src.application.github_sync_service import sync_github_repos
        from src.shared.config import Config

        config = Config()
        return sync_github_repos(config.database.url)

    @task()
    def get_repos() -> list[str]:
        """Get all tracked repo names from DB."""
        from src.infrastructure.github.github_repository import GitHubRepoRepository
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging("github_collect.get_repos")
        config = Config()
        repo_repository = GitHubRepoRepository(config.database.url)
        repos = repo_repository.find_all()
        names = [r.full_name for r in repos]
        logger.info("Found %d tracked repos: %s", len(names), names)
        return names

    @task()
    def collect_repo(repo_name: str) -> dict:
        """Collect PRs and issues for a single repository."""
        from src.application.github_collect_service import collect_repo as _collect_repo
        from src.infrastructure.github.github_repository import GitHubRepoRepository
        from src.shared.config import Config
        from src.shared.logging import setup_logging

        logger = setup_logging(f"github_collect.{repo_name}")
        config = Config()
        repo_repository = GitHubRepoRepository(config.database.url)
        repo = repo_repository.find_by_full_name(repo_name)
        if not repo:
            raise ValueError(f"Repo not found: {repo_name}")

        logger.info("[collect] repo=%s", repo_name)
        result = _collect_repo(config, repo)
        logger.info("[done] repo=%s prs=%d issues=%d", repo_name, result["prs_collected"], result["issues_collected"])
        return {
            "repo": repo_name,
            "prs": result["prs_collected"],
            "issues": result["issues_collected"],
        }

    @task(outlets=[github_collected])
    def summarize(results: list[dict]) -> None:
        """Log summary of all collection results."""
        from src.shared.logging import setup_logging

        logger = setup_logging("github_collect.summary")
        total_prs = sum(r["prs"] for r in results)
        total_issues = sum(r["issues"] for r in results)
        logger.info(
            "GitHub collect complete: %d repos, %d PRs, %d issues",
            len(results), total_prs, total_issues,
        )
        for r in results:
            logger.info("  %s: prs=%d issues=%d", r["repo"], r["prs"], r["issues"])

    sync_result = sync_repos()
    repos = get_repos()
    sync_result >> repos
    results = collect_repo.expand(repo_name=repos)
    summarize(results)


github_collect()
