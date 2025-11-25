.PHONY: help

# Check if 'uv' is installed
ifeq (, $(shell which uv))
$(error "uv is not installed. Please install it before running this Makefile.")
endif

# Default target - show available commands
help: # Show this help menu
	@echo "Available make commands:"
	@echo ""
	@awk 'BEGIN {FS = ":.*# "; printf "%-20s %s\n", "Target", "Description"} /^[a-zA-Z_-]+:.*# / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

dev: # Install development dependencies and package in editable mode
	uv sync --all-groups
	uv pip install -e .

update:
	uv sync --upgrade --all-groups
	uv lock --upgrade

proto: # TODO: auto-generate proto files
	@echo "TODO"

examples: dev # Pull in tetra-examples
	git submodule init
	git submodule update --remote
	@echo "🚀 Running make inside tetra-examples..."; \
	$(MAKE) -C tetra-examples

clean: # Remove build artifacts and cache files
	rm -rf dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean dev # Build PyPI Package
	uv build

validate-wheel: build # Validate wheel packaging
	@./scripts/validate-wheel.sh

security-scans: # Run security scans (informational)
	uv pip install bandit[toml] --quiet
	uv run bandit -r src/ -ll -x "**/tests/**" || echo "Security scan completed with issues (informational)"

# Test commands
test: # Run all tests
	uv run pytest tests/ -v

test-unit: # Run unit tests only
	uv run pytest tests/unit/ -v -m "not integration"

test-integration: # Run integration tests only
	uv run pytest tests/integration/ -v -m integration

test-coverage: # Run tests with coverage report
	uv run pytest tests/ -v --cov=tetra_rp --cov-report=term-missing

test-fast: # Run tests with fast-fail mode
	uv run pytest tests/ -v -x --tb=short

# Linting commands
lint: # Check code with ruff
	uv run ruff check .

lint-fix: # Fix code issues with ruff
	uv run ruff check . --fix

format: # Format code with ruff
	uv run ruff format .

format-check: # Check code formatting
	uv run ruff format --check .

# Type checking
typecheck: # Check types with mypy
	uv run mypy .

# Quality gates (used in CI)
quality-check: format-check lint test-coverage # Essential quality gate for CI
quality-check-strict: format-check lint typecheck test-coverage # Strict quality gate with type checking

# GitHub Actions specific targets
ci-quality-github: # Quality checks with GitHub Actions formatting
	@echo "::group::Code formatting check"
	uv run ruff format --check . 
	@echo "::endgroup::"
	@echo "::group::Linting"
	uv run ruff check . --output-format=github
	@echo "::endgroup::"
	@echo "::group::Test suite with coverage"
	uv run pytest tests/ --junitxml=pytest-results.xml -v --cov=tetra_rp --cov-report=term-missing
	@echo "::endgroup::"
