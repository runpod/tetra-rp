# Load .env vars from file before everything else
from dotenv import load_dotenv

load_dotenv()

from .logger import setup_logging  # noqa: E402

setup_logging()

# TYPE_CHECKING imports provide full IDE support (autocomplete, type hints)
# while __getattr__ enables lazy loading at runtime for fast CLI startup
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from .client import remote
    from .core.resources import (
        CpuInstanceType,
        CpuLiveServerless,
        CpuServerlessEndpoint,
        CudaVersion,
        DataCenter,
        GpuGroup,
        LiveServerless,
        NetworkVolume,
        PodTemplate,
        ResourceManager,
        ServerlessEndpoint,
        ServerlessType,
    )


def __getattr__(name):
    """Lazily import core modules only when accessed."""
    if name == "remote":
        from .client import remote

        return remote
    elif name in (
        "CpuServerlessEndpoint",
        "CpuInstanceType",
        "CpuLiveServerless",
        "CudaVersion",
        "DataCenter",
        "GpuGroup",
        "LiveServerless",
        "PodTemplate",
        "ResourceManager",
        "ServerlessEndpoint",
        "ServerlessType",
        "NetworkVolume",
    ):
        from .core.resources import (
            CpuServerlessEndpoint,
            CpuInstanceType,
            CpuLiveServerless,
            CudaVersion,
            DataCenter,
            GpuGroup,
            LiveServerless,
            PodTemplate,
            ResourceManager,
            ServerlessEndpoint,
            ServerlessType,
            NetworkVolume,
        )

        attrs = {
            "CpuServerlessEndpoint": CpuServerlessEndpoint,
            "CpuInstanceType": CpuInstanceType,
            "CpuLiveServerless": CpuLiveServerless,
            "CudaVersion": CudaVersion,
            "DataCenter": DataCenter,
            "GpuGroup": GpuGroup,
            "LiveServerless": LiveServerless,
            "PodTemplate": PodTemplate,
            "ResourceManager": ResourceManager,
            "ServerlessEndpoint": ServerlessEndpoint,
            "ServerlessType": ServerlessType,
            "NetworkVolume": NetworkVolume,
        }
        return attrs[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "remote",
    "CpuServerlessEndpoint",
    "CpuInstanceType",
    "CpuLiveServerless",
    "CudaVersion",
    "DataCenter",
    "GpuGroup",
    "LiveServerless",
    "PodTemplate",
    "ResourceManager",
    "ServerlessEndpoint",
    "ServerlessType",
    "NetworkVolume",
]
