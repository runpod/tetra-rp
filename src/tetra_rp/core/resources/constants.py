import os
import platform
from urllib.parse import urlparse

import runpod

CONSOLE_BASE_URL = os.environ.get("CONSOLE_BASE_URL", "https://console.runpod.io")
CONSOLE_URL = f"{CONSOLE_BASE_URL}/serverless/user/endpoint/%s"


def _endpoint_domain_from_base_url(base_url: str) -> str:
    if not base_url:
        return "api.runpod.ai"
    if "://" not in base_url:
        base_url = f"https://{base_url}"
    parsed = urlparse(base_url)
    return parsed.netloc or "api.runpod.ai"


ENDPOINT_DOMAIN = _endpoint_domain_from_base_url(runpod.endpoint_url_base)


def _get_platform_aware_tag(base_tag: str) -> str:
    """Get platform-specific image tag.

    For local/development tags, appends architecture suffix for arm64 machines.
    For production tags (latest, version numbers), uses as-is for manifest support.

    Args:
        base_tag: Base image tag (e.g., "local", "latest", "v1.0")

    Returns:
        Platform-specific tag (e.g., "local-arm64" on arm64, "local" on x86_64)
    """
    # Don't append architecture to production tags
    if base_tag in ("latest", "dev") or base_tag.startswith("v"):
        return base_tag

    # Detect platform and append architecture suffix for arm64
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return f"{base_tag}-arm64"

    return base_tag


# Docker image configuration
TETRA_IMAGE_TAG = os.environ.get("TETRA_IMAGE_TAG", "latest")
_RESOLVED_TAG = _get_platform_aware_tag(TETRA_IMAGE_TAG)

TETRA_GPU_IMAGE = os.environ.get("TETRA_GPU_IMAGE", f"runpod/tetra-rp:{_RESOLVED_TAG}")
TETRA_CPU_IMAGE = os.environ.get(
    "TETRA_CPU_IMAGE", f"runpod/tetra-rp-cpu:{_RESOLVED_TAG}"
)
TETRA_LB_IMAGE = os.environ.get("TETRA_LB_IMAGE", f"runpod/tetra-rp-lb:{_RESOLVED_TAG}")
TETRA_CPU_LB_IMAGE = os.environ.get(
    "TETRA_CPU_LB_IMAGE", f"runpod/tetra-rp-lb-cpu:{_RESOLVED_TAG}"
)

# Worker configuration defaults
DEFAULT_WORKERS_MIN = 1
DEFAULT_WORKERS_MAX = 3

# Flash app artifact upload constants
TARBALL_CONTENT_TYPE = "application/gzip"
MAX_TARBALL_SIZE_MB = 500  # Maximum tarball size in megabytes
VALID_TARBALL_EXTENSIONS = (".tar.gz", ".tgz")  # Valid tarball file extensions
GZIP_MAGIC_BYTES = (0x1F, 0x8B)  # Magic bytes for gzip files
