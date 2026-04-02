.PHONY: setup lint test eval db-up db-migrate

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	mypy src/

test:
	pytest -x --tb=short -q

eval:
	python -m sigint.eval.run --output results/latest.json

db-up:
	docker-compose up -d

db-migrate:
	alembic upgrade head
