.PHONY: help test test-unit test-integration test-fast coverage clean lint format install-dev

# Default target
help:
	@echo "Available commands:"
	@echo "  make test           - Run all tests with coverage"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-fast      - Run fast tests only (exclude slow)"
	@echo "  make coverage       - Generate coverage report"
	@echo "  make lint           - Run linting checks"
	@echo "  make format         - Format code with black and ruff"
	@echo "  make clean          - Clean test artifacts"
	@echo "  make install-dev     - Install development dependencies"

# Run all tests with coverage
test:
	pytest --cov=multi_provider_router --cov-report=term-missing --cov-report=html --cov-report=xml

# Run unit tests only
test-unit:
	pytest -m unit --cov=multi_provider_router --cov-report=term-missing

# Run integration tests only
test-integration:
	pytest -m integration --cov=multi_provider_router --cov-report=term-missing

# Run fast tests only
test-fast:
	pytest -m "not slow" --cov=multi_provider_router --cov-report=term-missing

# Generate coverage report
coverage:
	pytest --cov=multi_provider_router --cov-report=html --cov-report=term-missing --cov-report=xml
	@echo "Coverage report generated in htmlcov/"

# Run linting
lint:
	ruff check multi_provider_router tests
	mypy multi_provider_router

# Format code
format:
	black multi_provider_router tests
	ruff check --fix multi_provider_router tests

# Clean test artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage

# Install development dependencies
install-dev:
	pip install -e ".[dev]"

# Run specific test file
test-file:
	@read -p "Enter test file path (e.g., tests/test_providers.py): " file; \
	pytest $$file -v

# Run tests matching pattern
test-pattern:
	@read -p "Enter test pattern (e.g., glm): " pattern; \
	pytest -k $$pattern -v
