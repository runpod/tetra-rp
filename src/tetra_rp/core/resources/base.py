import hashlib
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class BaseResource(BaseModel):
    """Base class for all resources."""

    id: Optional[str] = None

    @property
    def resource_id(self) -> str:
        """Unique resource ID based on configuration."""
        resource_type = self.__class__.__name__
        config_str = self.model_dump_json(exclude_none=True)
        hash_obj = hashlib.md5(f"{resource_type}:{config_str}".encode())
        return f"{resource_type}_{hash_obj.hexdigest()}"


class DeployableResource(BaseResource, ABC):
    """Base class for deployable resources."""

    @property
    @abstractmethod
    def url(self) -> str:
        """Public URL of the resource."""
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def deploy(self) -> "DeployableResource":
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
