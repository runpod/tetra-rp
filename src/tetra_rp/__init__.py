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
    DataCenter,
    GpuGroup,
    LiveServerless,
    LoadBalancerSlsResource,
    PodTemplate,
    ResourceManager,
    ServerlessResource,
    ServerlessEndpoint,
    runpod,
    NetworkVolume,
)
from .core.resources.load_balancer_sls import LoadBalancerSls, endpoint  # noqa: E402


__all__ = [
    "remote",
    "CpuServerlessEndpoint",
    "CpuInstanceType",
    "CudaVersion",
    "DataCenter",
    "GpuGroup",
    "LiveServerless", 
    "LoadBalancerSlsResource",
    "PodTemplate",
    "ResourceManager",
    "ServerlessResource",
    "ServerlessEndpoint",
    "runpod",
    "NetworkVolume",
    "LoadBalancerSls",
    "endpoint",
]
