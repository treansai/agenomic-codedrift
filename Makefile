.PHONY: install test lint typecheck e2e bundle clean ci

install:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check src tests

typecheck:
	mypy src/agenomic_codedrift

ci: lint typecheck test

e2e:
	@test -n "$$ANTHROPIC_API_KEY" || (echo "ANTHROPIC_API_KEY required" && exit 1)
	@test -n "$$AGENOMIC_API_KEY"   || (echo "AGENOMIC_API_KEY required"   && exit 1)
	@test -n "$$AGENOMIC_ENDPOINT"  || (echo "AGENOMIC_ENDPOINT required"  && exit 1)
	python -m agenomic_codedrift run --benchmark-dir benchmarks --baseline-path baseline.jsonl

bundle:
	python scripts/build_and_push_bundle.py

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache **/__pycache__
