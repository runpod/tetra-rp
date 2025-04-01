import os
import runpod
from .base import DeployableResource
from .gpu import GpuType, GpuTypeDetail, GpuGroups
from .serverless import ServerlessResource
from .template import TemplateResource
from .utils import inquire


runpod.api_key = os.getenv("RUNPOD_API_KEY")


__all__ = [
    "inquire",
    "runpod",
    "DeployableResource",
    "GpuType",
    "GpuTypeDetail",
    "GpuGroups",
    "ServerlessResource",
    "TemplateResource",
]
