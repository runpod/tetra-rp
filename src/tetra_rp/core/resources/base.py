import hashlib
from abc import ABC, abstractmethod
from typing import Optional, ClassVar
from pydantic import BaseModel, ConfigDict, computed_field

class BaseResource(BaseModel):
    """Base class for all resources."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_default=True,
        serialize_by_alias=True,
    )

    id: Optional[str] = None
    _hashed_fields: ClassVar[set] = set()
    
    # diffed fields is a temporary holder for fields that are "out of sync" -
    # where a local instance representation of an endpoint is not up to date with the remote resource.
    # it's needed for determining how updates are applied (eg, if we need to update a pod template)
    fields_to_update: set[str] = set()

    
    @computed_field
    @property
    def resource_hash(self) -> str:
        """Unique resource ID based on configuration."""
        resource_type = self.__class__.__name__
        # don't self reference and exclude any deployment state (eg id)
        config_str = self.model_dump_json(include=self.__class__._hashed_fields)
        hash_obj = hashlib.md5(f"{resource_type}:{config_str}".encode())
        return f"{resource_type}_{hash_obj.hexdigest()}"

    @property
    def resource_id(self) -> str:
        """Logical Tetra resource id defined by resource type and name.
        Distinct from a server-side Runpod id. 
        """
        resource_type = self.__class__.__name__
        # TODO: eventually we could namespace this to user ids or team ids
        if not self.name:
            self.name = "unnamed"
        return f"{resource_type}_{self.name}"


class DeployableResource(BaseResource, ABC):
    """Base class for deployable resources."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    @property
    @abstractmethod
    def url(self) -> str:
        """Public URL of the resource."""
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def is_deployed(self) -> bool:
        """Check the resource if it's still valid or available."""
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    async def deploy(self) -> "DeployableResource":
        """Deploy the resource."""
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    async def update(self) -> "DeployableResource":
        """Update the resource."""
        raise NotImplementedError("Subclasses should implement this method.")
