from .logger import setup_logging
setup_logging()

from . import remote_execution_pb2, remote_execution_pb2_grpc
from .core.resources.resource_manager import ResourceManager
from .core.resources.serverless import ServerlessResource
from .client import remote

__all__ = [
    "remote",
    "remote_execution_pb2",
    "remote_execution_pb2_grpc",
    "ResourceManager",
    "ServerlessResource",
]
