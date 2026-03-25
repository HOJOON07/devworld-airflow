.PHONY: up down build logs test lint format clean db-reset dag-apply dag-list articles-reset

# Docker
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-scheduler:
	docker compose logs -f airflow-scheduler

logs-webserver:
	docker compose logs -f airflow-webserver

# Test
test:
	python -m pytest tests/unit/ -v

test-all:
	python -m pytest tests/ -v

# Lint / Format
lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	black .

# DB
db-reset:
	docker compose down -v
	docker compose up -d postgres
	@echo "Waiting for postgres..."
	@sleep 3
	docker compose up -d

# Airflow DAG
dag-apply:
	docker compose exec airflow-scheduler airflow dags reserialize

dag-list:
	docker compose exec airflow-scheduler airflow dags list

# Articles
articles-reset:
	docker compose exec postgres psql -U airflow -d app_db -c "DELETE FROM articles; DELETE FROM crawl_jobs"

articles-reset-source:
	@test -n "$(SOURCE)" || (echo "Usage: make articles-reset-source SOURCE=toss-tech" && exit 1)
	docker compose exec postgres psql -U airflow -d app_db -c "DELETE FROM articles WHERE source_id = (SELECT id FROM crawl_sources WHERE name='$(SOURCE)'); DELETE FROM crawl_jobs WHERE source_id = (SELECT id FROM crawl_sources WHERE name='$(SOURCE)');"

# DuckDB UI (로컬 실행)
duckdb-ui:
	python3 scripts/duckdb-ui.py

# Clean
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
