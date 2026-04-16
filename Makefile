.PHONY: install dev lint format test test-fast test-cov migrate migration downgrade \
        up down reset-db build run-docker clean setup

# ── First-time setup ──────────────────────────────────────────────────────────
setup:
	@echo "Setting up local development environment..."
	cp -n .env.local .env || true
	pip install -e ".[dev]"
	pip install bcrypt
	docker compose up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 3
	alembic upgrade head
	@echo ""
	@echo "✓ Ready! Run: make dev"
	@echo "  API:     http://localhost:8000"
	@echo "  Docs:    http://localhost:8000/docs"
	@echo "  Mailpit: http://localhost:8025"
	@echo "  MinIO:   http://localhost:9001  (user: minioadmin / minioadmin)"

# ── Dependencies ──────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"
	pip install bcrypt

# ── Docker (local services) ───────────────────────────────────────────────────
up:
	docker compose up -d
	@echo "✓ Postgres:  localhost:5432"
	@echo "✓ MinIO API: localhost:9000  UI: localhost:9001"
	@echo "✓ Mailpit:   localhost:8025"

down:
	docker compose down

reset-db:
	docker compose down -v
	docker compose up -d postgres
	@sleep 3
	alembic upgrade head
	@echo "✓ Database reset complete"

# ── Local dev server ──────────────────────────────────────────────────────────
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check app/ tests/
	ruff check . --fix && ruff format .

format:
	black app/ tests/
	ruff check --fix app/ tests/

check: lint
	black --check app/ tests/

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest

test-fast:
	pytest -x --no-cov

test-cov:
	pytest --cov=app --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ── Database / Alembic ────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migration:
	@read -p "Migration description: " desc; \
	alembic revision --autogenerate -m "$$desc"

downgrade:
	alembic downgrade -1

# ── Docker image ──────────────────────────────────────────────────────────────
build:
	docker build -t gatherease-backend:local .

run-docker:
	docker run --env-file .env -p 8000:8000 gatherease-backend:local

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage
