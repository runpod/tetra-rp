# Ship serverless code as you write it. No builds, no deploys — just run.
import os
from .serverless import ServerlessResource
from .template import PodTemplate


TETRA_GPU_IMAGE = os.environ.get("TETRA_GPU_IMAGE", "runpod/tetra-rp:dev")
TETRA_CPU_IMAGE = os.environ.get("TETRA_CPU_IMAGE", "runpod/tetra-rp-cpu:dev")


class LiveServerless(ServerlessResource):
    def __init__(self, **data):
        if data.get("instanceIds", False):
            default_template = TETRA_CPU_IMAGE
        else:
            default_template = TETRA_GPU_IMAGE

        if template := data.get("template"):
            template.imageName = default_template
        else:
            template = PodTemplate(imageName=default_template)
        data["template"] = template

        super().__init__(**data)
