# Ship serverless code as you write it. No builds, no deploys — just run.
import os
from .serverless import ServerlessResource
from .template import PodTemplate


TETRA_GPU_IMAGE = os.environ.get("TETRA_GPU_IMAGE", "runpod/tetra-rp:dev")


class LiveServerless(ServerlessResource):
    def __init__(self, **data):
        if template := data.get("template"):
            template.imageName = TETRA_GPU_IMAGE
        else:
            template = PodTemplate(
                imageName=TETRA_GPU_IMAGE,
            )
        data["template"] = template
        super().__init__(**data)
