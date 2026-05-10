.PHONY: help install install-dev test test-cov lint format clean build run

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install production dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -r requirements-dev.txt
	pre-commit install

test:  ## Run tests
	python -m pytest tests/ -v

test-cov:  ## Run tests with coverage
	python -m pytest tests/ --cov=generation --cov-report=term-missing --cov-report=html

lint:  ## Run linting
	black --check .
	isort --check-only .
	flake8 .
	mypy generation/

format:  ## Format code
	black .
	isort .

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -f .coverage coverage.xml
	rm -rf build/ dist/

build:  ## Build the package
	python -m build

run:  ## Run the application
	python app.py

run-celery:  ## Run Celery worker
	celery -A celery_tasks worker -Q generation_priority,generation_normal --pool=gevent --concurrency=100 --loglevel=info

security:  ## Run security checks
	bandit -r generation/ app.py celery_tasks.py
	safety check -r requirements.txt

docs:  ## Generate documentation
	cd docs && make html

docker-build:  ## Build Docker image
	docker build -t aiimagenew:latest .

docker-run:  ## Run Docker container
	docker run -p 5078:5078 aiimagenew:latest

pre-commit:  ## Run pre-commit on all files
	pre-commit run --all-files

check-all: lint test security  ## Run all checks

.DEFAULT_GOAL := help
