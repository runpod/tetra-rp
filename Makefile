IMAGE = runpod/tetrarc
TAG = latest
FULL_IMAGE = $(IMAGE):$(TAG)

.PHONY: build requirements

build: requirements
	docker buildx build \
	--no-cache \
	--platform linux/amd64 \
	-t $(FULL_IMAGE) \
	. --load

requirements:
	poetry self show plugins | grep -q export || poetry self add poetry-plugin-export
	poetry export --without-hashes --without dev -f requirements.txt > requirements.txt

push:
	docker push $(FULL_IMAGE)

proto:
# TODO: auto-generate proto files
