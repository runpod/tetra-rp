import hashlib
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, ConfigDict, PrivateAttr


class BaseResource(BaseModel):
    """Base class for all resources."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_default=True,
        serialize_by_alias=True,
    )

    id: Optional[str] = None
    _resource_id: Optional[str] = PrivateAttr(default=None)

    @property
    def resource_id(self) -> str:
        """Unique resource ID based on configuration.

        Computed once and cached to ensure stability across the object's lifetime.
        This prevents hash changes if validators mutate the object after first access.

        The hash excludes the 'id' field since it's assigned by the provider after
        deployment and should not affect resource identity.
        """
        if self._resource_id is None:
            resource_type = self.__class__.__name__
            # Exclude 'id' field from hash - it's assigned post-deployment
            config_str = self.model_dump_json(exclude_none=True, exclude={"id"})
            hash_obj = hashlib.md5(f"{resource_type}:{config_str}".encode())
            self._resource_id = f"{resource_type}_{hash_obj.hexdigest()}"
        return self._resource_id

    @property
    def config_hash(self) -> str:
        """Get hash of current configuration (excluding id).

        Unlike resource_id which is cached, this always computes fresh hash.
        Used for drift detection.
        """
        resource_type = self.__class__.__name__
        config_str = self.model_dump_json(exclude_none=True, exclude={"id"})
        hash_obj = hashlib.md5(f"{resource_type}:{config_str}".encode())
        return hash_obj.hexdigest()

    def get_resource_key(self) -> str:
        """Get stable resource key for tracking.

        Format: {ResourceType}:{name}
        This provides stable identity even when config changes.
        """
        resource_type = self.__class__.__name__
        name = getattr(self, "name", None)
        if name:
            return f"{resource_type}:{name}"
        # Fallback to resource_id for resources without names
        return self.resource_id


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
    async def undeploy(self) -> bool:
        """Undeploy/delete the resource.

        Returns:
            True if successfully undeployed, False otherwise
        """
        raise NotImplementedError("Subclasses should implement this method.")
