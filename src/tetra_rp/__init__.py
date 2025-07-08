# Load .env vars from file
# before everything else
from dotenv import load_dotenv

load_dotenv()


from .logger import setup_logging  # noqa: E402

setup_logging()

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
from .core.utils.rich_ui import capture_local_prints


__all__ = [
    "remote",
    "capture_local_prints",
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
