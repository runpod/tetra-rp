# Load .env vars from file
# before everything else
from dotenv import load_dotenv

load_dotenv()

from .client import remote  # noqa: E402
from .core.resources import (  # noqa: E402
    CpuServerlessEndpoint,
    CpuInstanceType,
    CudaVersion,
    GpuGroup,
    LiveServerless,
    PodTemplate,
    ResourceManager,
    ServerlessEndpoint,
    runpod,
)


__all__ = [
    "remote",
    "CpuServerlessEndpoint",
    "CpuInstanceType",
    "CudaVersion",
    "GpuGroup",
    "LiveServerless",
    "PodTemplate",
    "ResourceManager",
    "ServerlessEndpoint",
    "runpod",
]
