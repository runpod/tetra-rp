IMAGE = runpod/tetrarc
TAG = latest
FULL_IMAGE = $(IMAGE):$(TAG)

.PHONY: dev

# Check if 'uv' is installed
ifeq (, $(shell which uv))
$(error "uv is not installed. Please install it before running this Makefile.")
endif

dev:
	uv sync --all-groups
	make examples

build: requirements
	docker buildx build \
	--no-cache \
	--platform linux/amd64 \
	-t $(FULL_IMAGE) \
	. --load

requirements:
	uv pip compile pyproject.toml > requirements.txt

push:
	docker push $(FULL_IMAGE)

proto:
# TODO: auto-generate proto files

examples:
	git submodule init
	git submodule update
	@echo "🚀 Running make inside tetra-examples..."; \
	$(MAKE) -C tetra-examples
