import hashlib
from abc import ABC, abstractmethod
from pydantic import BaseModel


class DeployableResource(BaseModel):
class DeployableResource(BaseModel, ABC):
    """Base class for cloud resources."""

    @abstractmethod
    async def deploy(self) -> BaseModel:
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
