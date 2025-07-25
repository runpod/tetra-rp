# Ship serverless code as you write it. No builds, no deploys — just run.
import os
from pydantic import model_validator
from .serverless import ServerlessEndpoint

TETRA_IMAGE_TAG = os.environ.get("TETRA_IMAGE_TAG", "latest")
TETRA_GPU_IMAGE = os.environ.get(
    "TETRA_GPU_IMAGE", f"runpod/tetra-rp:{TETRA_IMAGE_TAG}"
)
TETRA_CPU_IMAGE = os.environ.get(
    "TETRA_CPU_IMAGE", f"runpod/tetra-rp-cpu:{TETRA_IMAGE_TAG}"
)


class LiveServerless(ServerlessEndpoint):
    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default templates for Live Serverless. This can't be changed."""
        # Always set imageName based on instanceIds presence
        data["imageName"] = (
            TETRA_CPU_IMAGE if data.get("instanceIds") else TETRA_GPU_IMAGE
        )
        return data

    @property
    def imageName(self):
        # Lock imageName to always reflect instanceIds
        return (
            TETRA_CPU_IMAGE if getattr(self, "instanceIds", None) else TETRA_GPU_IMAGE
        )

    @imageName.setter
    def imageName(self, value):
        # Prevent manual setting of imageName
        pass
