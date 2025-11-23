.PHONY: help install dev test lint format clean docker-build docker-up docker-down init sync

help:
	@echo "HelpScout Ticket Insights - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install      Install dependencies"
	@echo "  make dev          Run development server"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linters"
	@echo "  make format       Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build Build Docker images"
	@echo "  make docker-up    Start all services"
	@echo "  make docker-down  Stop all services"
	@echo "  make init         Initialize database and run first sync"
	@echo "  make sync         Run manual sync"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        Remove cache and temp files"

install:
	pip install -r requirements.txt

dev:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	flake8 src tests --max-line-length=100 --extend-ignore=E203,W503
	black --check src tests
	isort --check-only src tests

format:
	black src tests
	isort src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete
	rm -rf htmlcov/

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

init:
	docker compose exec api python scripts/init_db.py

sync:
	docker compose exec api python scripts/run_sync.py

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	@read -p "Migration name: " name; \
	docker compose exec api alembic revision --autogenerate -m "$$name"
