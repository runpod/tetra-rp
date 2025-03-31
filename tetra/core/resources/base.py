import hashlib
from pydantic import BaseModel


class DeployableResource(BaseModel):
    """Base class for cloud resources."""

    def deploy(self) -> BaseModel:
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
