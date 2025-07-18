.PHONY: dev

# Check if 'uv' is installed
ifeq (, $(shell which uv))
$(error "uv is not installed. Please install it before running this Makefile.")
endif

dev:
	uv sync --all-groups

proto:
# TODO: auto-generate proto files

examples: dev
	git submodule init
	git submodule update --remote
	@echo "🚀 Running make inside tetra-examples..."; \
	$(MAKE) -C tetra-examples

clean:
	rm -rf dist build *.egg-info .tetra_resources.pkl
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean dev
	uv build

check: dev
	@echo "Running code quality checks..."
	@echo "Linting with ruff..."
	uv run ruff check src/ tests/ --output-format=github
	@echo "Checking formatting with ruff..."
	uv run ruff format --check src/ tests/
	@echo "Type checking with mypy..."
	uv run mypy src/tetra_rp --show-error-codes --pretty || true
	@echo "Security scanning with bandit..."
	uv pip install bandit[toml] --quiet
	uv run bandit -r src/ -ll -x "**/tests/**" || true
	@echo "Running test suite..."
	uv run pytest tests/
	@echo "All checks completed!"

check-strict: dev
	@echo "Running strict code quality checks (CI mode)..."
	uv run ruff check src/ tests/ --output-format=github
	uv run ruff format --check src/ tests/
	uv run mypy src/tetra_rp --show-error-codes --pretty
	uv pip install bandit[toml] --quiet
	uv run bandit -r src/ -ll -x "**/tests/**"
	uv run pytest tests/
