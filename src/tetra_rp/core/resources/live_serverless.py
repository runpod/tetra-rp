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
        # Check if custom image was set in the raw field (__dict__)
        # This happens during model construction before template is created
        if "__dict__" in dir(self) and "imageName" in self.__dict__:
            custom = self.__dict__["imageName"]
            if custom and custom != self._live_image:
                return custom
        # After template creation, check template.imageName
        if (
            hasattr(self, "template")
            and self.template
            and hasattr(self.template, "imageName")
        ):
            custom = self.template.imageName
            if custom and custom != self._live_image:
                return custom
        return self._live_image

    @imageName.setter
    def imageName(self, value):
        # Store in template.imageName for production mode
        if not hasattr(self, "template") or not self.template:
            from .template import PodTemplate

            self.template = PodTemplate(imageName=value)
        else:
            self.template.imageName = value


class LiveServerless(LiveServerlessMixin, ServerlessEndpoint):
    """GPU-only live serverless endpoint."""

    @property
    def _live_image(self) -> str:
        return TETRA_GPU_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default GPU image for Live Serverless."""
        # Only set default if imageName is not provided
        # If custom imageName IS provided, let it through (for production mode)
        if "imageName" not in data or not data["imageName"]:
            data["imageName"] = TETRA_GPU_IMAGE
        # Otherwise keep the custom value - it will be used to create the template
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
        # Only set default if imageName is not provided
        if "imageName" not in data or not data["imageName"]:
            data["imageName"] = TETRA_CPU_IMAGE
        # Custom imageName will be stored in template during model construction
        return data
