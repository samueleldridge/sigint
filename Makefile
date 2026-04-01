.PHONY: setup lint test eval

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	mypy src/

test:
	pytest -x --tb=short -q

eval:
	python -m sigint.eval.run --output results/latest.json