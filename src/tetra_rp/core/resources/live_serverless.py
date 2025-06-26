# Ship serverless code as you write it. No builds, no deploys — just run.
import os
from pydantic import model_validator
from .serverless import ServerlessResource


TETRA_GPU_IMAGE = os.environ.get("TETRA_GPU_IMAGE", "runpod/tetra-rp:dev")
TETRA_CPU_IMAGE = os.environ.get("TETRA_CPU_IMAGE", "runpod/tetra-rp-cpu:dev")


class LiveServerless(ServerlessResource):
    @model_validator(mode="before")
    def set_default_template(self: dict) -> dict:
        """Set default templates for Live Serverless. This can't be changed."""
        self["imageName"] = TETRA_CPU_IMAGE if self.get("instanceIds") else TETRA_GPU_IMAGE
        return self
