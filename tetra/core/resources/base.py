import hashlib
from abc import ABC, abstractmethod
from pydantic import BaseModel


class DeployableResource(BaseModel, ABC):
    """Base class for cloud resources."""
    @property
    def resource_id(self) -> str:
        """Unique resource ID based on configuration."""
        resource_type = self.__class__.__name__
        config_str = self.model_dump_json(exclude_none=True)
        hash_obj = hashlib.md5(f"{config_str}:{resource_type}".encode())
        return f"{resource_type}_{hash_obj.hexdigest()}"


    @abstractmethod
    async def deploy(self) -> BaseModel:
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
