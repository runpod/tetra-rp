.PHONY: dev

# Check if 'uv' is installed
ifeq (, $(shell which uv))
$(error "uv is not installed. Please install it before running this Makefile.")
endif

dev:
	uv sync --all-groups
	make examples

proto:
# TODO: auto-generate proto files

examples:
	git submodule init
	git submodule update --remote
	@echo "🚀 Running make inside tetra-examples..."; \
	$(MAKE) -C tetra-examples
