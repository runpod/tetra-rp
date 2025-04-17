import os
from .logger import setup_logging
setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

from .core.resources.resource_manager import ResourceManager
from .core.resources.live_serverless import LiveServerless
from .core.resources.serverless import ServerlessResource
from .client import remote

__all__ = [
    "remote",
    "LiveServerless",
    "ResourceManager",
    "ServerlessResource",
]
