.PHONY: up down build logs test lint format clean db-reset

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

# Clean
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
