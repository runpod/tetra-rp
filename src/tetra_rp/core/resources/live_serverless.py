# Ship serverless code as you write it. No builds, no deploys — just run.
import os
from pydantic import model_validator
from .serverless import ServerlessEndpoint
from .serverless_cpu import CpuServerlessEndpoint

TETRA_IMAGE_TAG = os.environ.get("TETRA_IMAGE_TAG", "latest")
TETRA_GPU_IMAGE = os.environ.get(
    "TETRA_GPU_IMAGE", f"runpod/tetra-rp:{TETRA_IMAGE_TAG}"
)
TETRA_CPU_IMAGE = os.environ.get(
    "TETRA_CPU_IMAGE", f"runpod/tetra-rp-cpu:{TETRA_IMAGE_TAG}"
)


class LiveServerlessMixin:
    """Common mixin for live serverless endpoints that locks the image."""

    @property
    def _live_image(self) -> str:
        """Override in subclasses to specify the locked image."""
        raise NotImplementedError("Subclasses must define _live_image")

    @property
    def imageName(self):
        # Lock imageName to specific image
        return self._live_image

    @imageName.setter
    def imageName(self, value):
        # Prevent manual setting of imageName
        pass


class LiveServerless(LiveServerlessMixin, ServerlessEndpoint):
    """GPU-only live serverless endpoint."""

    @property
    def _live_image(self) -> str:
        return TETRA_GPU_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default GPU image for Live Serverless."""
        data["imageName"] = TETRA_GPU_IMAGE
        return data


class CpuLiveServerless(LiveServerlessMixin, CpuServerlessEndpoint):
    """CPU-only live serverless endpoint with automatic disk sizing."""

    @property
    def _live_image(self) -> str:
        return TETRA_CPU_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default CPU image for Live Serverless."""
        data["imageName"] = TETRA_CPU_IMAGE
        return data
