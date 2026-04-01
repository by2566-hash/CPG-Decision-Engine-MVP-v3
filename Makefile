.PHONY: install test lint typecheck run clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src/decision_engine --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/decision_engine/

run:
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
