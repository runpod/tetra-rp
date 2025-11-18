# Contributing to tetra-rp

## Development Setup

### Prerequisites

- Python 3.9+ (3.12 recommended)
- uv package manager
- Git

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/your-org/tetra-rp.git
cd tetra-rp

# Install dependencies and package in editable mode
make dev
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
RUNPOD_API_KEY=your_api_key_here
```

Get your API key from: https://docs.runpod.io/get-started/api-keys

**When is the API key needed?**
- Remote execution features (`@remote` decorator)
- Resource deployment and management
- Integration tests that interact with Runpod API

**When is the API key NOT needed?**
- Local development with `flash run` (local server only)
- `flash init` command (project scaffolding)
- Unit tests (mocked API calls)
- Code formatting, linting, type checking

If you don't have an API key, you can still:
- Run unit tests: `make test-unit`
- Format and lint code: `make format lint`
- Work on CLI commands and local features
- Build and validate packages: `make build`

## Code Standards

### Type Hints Required

All functions must have type hints:

```python
# Required
def process_data(items: list[dict[str, Any]]) -> pd.DataFrame:
    """Process items and return DataFrame."""
    pass

# Not acceptable
def process_data(items):
    pass
```

### Error Handling Pattern

Use specific exceptions with context:

```python
# Correct
try:
    result = external_api_call()
except requests.HTTPError as e:
    logger.error(f"API call failed: {e.response.status_code}")
    raise ServiceUnavailableError(f"External service error: {e}") from e

# Incorrect
try:
    result = external_api_call()
except:
    print("Error occurred")
```

### Testing Requirements

Write tests before implementation (TDD approach):

1. Write failing test
2. Implement minimum code to pass test
3. Refactor while keeping tests green

All new features require:
- Unit tests in [tests/unit/](tests/unit/)
- Integration tests if external dependencies involved
- Minimum 35% code coverage (aim for 70% on critical paths)

Test structure follows Arrange-Act-Assert pattern:

```python
def test_user_creation():
    # Arrange
    user_data = {"email": "test@example.com", "name": "Test User"}

    # Act
    user = User.create(**user_data)

    # Assert
    assert user.email == user_data["email"]
    assert user.id is not None
```

## Development Workflow

### Making Changes

1. Create feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. Make changes following code standards

3. Run quality checks locally:
   ```bash
   # Format and lint
   make format
   make lint

   # Type checking
   make typecheck

   # Tests with coverage
   make test-coverage

   # Run all quality checks
   make quality-check
   ```

### Available Make Targets

```bash
make help                 # Show all available commands
make dev                  # Install development dependencies
make test                 # Run all tests
make test-unit            # Run unit tests only
make test-integration     # Run integration tests
make test-coverage        # Run tests with coverage report
make test-fast            # Run tests with fast-fail mode
make format               # Format code with ruff
make format-check         # Check code formatting
make lint                 # Check code with ruff
make lint-fix             # Auto-fix linting issues
make typecheck            # Check types with mypy
make quality-check        # Essential quality checks (CI)
make build                # Build PyPI package
make validate-wheel       # Validate wheel packaging
make clean                # Remove build artifacts
```

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automated versioning and changelog generation.

### Format

```
<type>: <description>

[optional body]

[optional footer]
```

### Types

| Type | Version Bump | Use Case |
|------|-------------|----------|
| `feat` | Minor | New feature |
| `fix` | Patch | Bug fix |
| `perf` | Patch | Performance improvement |
| `refactor` | Patch | Code refactoring |
| `docs` | Patch | Documentation |
| `test` | Patch | Tests |
| `build` | Patch | Build system |
| `ci` | Patch | CI configuration |
| `chore` | Patch | Maintenance |

### Breaking Changes

For breaking changes, add `!` after type or include `BREAKING CHANGE:` in footer:

```bash
# Option 1
feat!: redesign API interface

# Option 2
feat: add new authentication method

BREAKING CHANGE: The old auth method is no longer supported
```

### Examples

```bash
# Good
feat: add @remote decorator for CPU endpoints
fix: resolve memory leak in resource cleanup
docs: update installation instructions
refactor: simplify resource manager singleton

# Bad
Update readme                  # Missing type
feat add new feature           # Missing colon
Fix: bug in client             # Incorrect capitalization
```

## Pull Request Process

### Before Submitting

1. Ensure all tests pass: `make test`
2. Verify code quality: `make quality-check`
3. Update documentation if needed
4. Add tests for new functionality

### PR Requirements

- Use conventional commit format in PR title
- Provide clear description of changes
- Link related issues
- Ensure CI checks pass (blocks merge if failing)
- Request review from maintainers

### CI Quality Gates

All PRs run quality gates on Python 3.9, 3.10, 3.11, 3.12, and 3.13:

1. Code formatting check (ruff)
2. Linting (ruff)
3. Test suite with coverage
4. Package build verification

PRs cannot merge if any check fails.

## Testing Guide

### Quick Reference

```bash
# Development (fast iteration)
uv pip install -e .

# Development (complete packaging test)
make validate-wheel

# Unit tests
make test-unit

# Code quality
make quality-check
```

### Test Types

| Test Type | Command | Use Case |
|-----------|---------|----------|
| Editable install | `uv pip install -e .` | Fast iteration |
| Wheel install | `make validate-wheel` | Pre-release validation |
| Unit tests | `make test-unit` | Test code logic |
| Integration tests | `make test-integration` | Test external dependencies |

### Known Issues

**Editable installs hide packaging problems**
- Files read directly from source
- Always run `make validate-wheel` before releasing

**Coverage threshold failures**
- Use `--no-cov` flag: `uv run pytest tests/unit/test_file.py -v --no-cov`
- Or test specific module: `uv run pytest --cov=src/tetra_rp/module`

## Release Process

This project uses automated releases via Release Please. See [RELEASE_SYSTEM.md](RELEASE_SYSTEM.md) for complete details.

### Summary

1. Merge PRs with conventional commits to `main`
2. Release Please automatically creates/updates release PR
3. Review and merge release PR
4. Package automatically published to PyPI

### Version Bumping

- Major (1.0.0 → 2.0.0): Breaking changes (`feat!:`, `fix!:`)
- Minor (1.0.0 → 1.1.0): New features (`feat:`)
- Patch (1.0.0 → 1.0.1): Bug fixes (`fix:`)

## Code Review Guidelines

When reviewing code, consider:

- Would a new team member understand this in 6 months?
- What could break this code?
- Are there security implications?
- Is this the simplest solution that works?
- Are type hints present and accurate?
- Are tests comprehensive?

## Getting Help

- Check existing [Issues](https://github.com/your-org/tetra-rp/issues)
- Review [README.md](README.md) for usage examples
- See [TESTING.md](TESTING.md) for testing details
- See [RELEASE_SYSTEM.md](RELEASE_SYSTEM.md) for release process

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
