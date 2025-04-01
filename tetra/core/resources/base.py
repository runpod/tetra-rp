import hashlib
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class DeployableResource(BaseModel, ABC):
    """Base class for cloud resources."""
    id: Optional[str] = None

    @property
    def resource_id(self) -> str:
        """Unique resource ID based on configuration."""
        resource_type = self.__class__.__name__
        config_str = self.model_dump_json(exclude_none=True)
        hash_obj = hashlib.md5(f"{config_str}:{resource_type}".encode())
        return f"{resource_type}_{hash_obj.hexdigest()}"

    @property
    @abstractmethod
    def url(self) -> str:
        """Public URL of the resource."""
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    async def deploy(self) -> BaseModel:
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
