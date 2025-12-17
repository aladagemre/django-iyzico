.PHONY: help install test lint format clean build publish docs

help:
	@echo "django-iyzico development commands:"
	@echo "  make install    - Install package in development mode"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters (flake8, mypy)"
	@echo "  make format     - Format code (black, isort)"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make build      - Build package"
	@echo "  make publish    - Publish to PyPI"
	@echo "  make docs       - Build documentation"

install:
	pip install -e ".[dev]"

test:
	pytest

test-cov:
	pytest --cov=django_iyzico --cov-report=html --cov-report=term

lint:
	flake8 django_iyzico tests
	mypy django_iyzico

format:
	black django_iyzico tests
	isort django_iyzico tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

publish: build
	python -m twine upload dist/*

publish-test: build
	python -m twine upload --repository testpypi dist/*

docs:
	cd docs && make html
