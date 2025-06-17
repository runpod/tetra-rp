PYPI_TOKEN := $(shell python -c "import configparser; c=configparser.ConfigParser(); c.read('$(HOME)/.pypirc'); print(c.get('pypi', 'password', fallback=''))" 2>/dev/null)

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

publish-test: build
	@if [ -z "$(PYPI_TOKEN)" ]; then \
		echo "Error: No PyPI token found in ~/.pypirc"; \
		exit 1; \
	fi

publish: build
	UV_PUBLISH_TOKEN=$(PYPI_TOKEN) uv publish
