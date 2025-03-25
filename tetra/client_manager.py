from typing import Optional
from .client import RemoteExecutionClient


class GlobalClientManager:
    _instance: Optional[RemoteExecutionClient] = None

    @classmethod
    def get_client(cls) -> RemoteExecutionClient:
        if cls._instance is None:
            cls._instance = RemoteExecutionClient()
        return cls._instance


def get_global_client() -> RemoteExecutionClient:
    return GlobalClientManager.get_client()
