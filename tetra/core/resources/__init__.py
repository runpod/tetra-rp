import os
import runpod
from .base import DeployableResource
from .gpu import GpuType, GpuTypeDetail, GpuGroups
from .serverless import ServerlessResource, ServerlessResourceInput
from .template import TemplateResource


runpod.api_key = os.getenv("RUNPOD_API_KEY")


__all__ = [
    "runpod",
    "DeployableResource",
    "GpuType",
    "GpuTypeDetail",
    "GpuGroups",
    "ServerlessResource",
    "ServerlessResourceInput",
    "TemplateResource",
]
