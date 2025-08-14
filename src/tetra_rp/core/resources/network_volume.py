import hashlib
import logging
from enum import Enum
from typing import Optional

from pydantic import (
    Field,
    field_serializer,
)

from ..api.runpod import RunpodRestClient
from .base import DeployableResource
from .constants import CONSOLE_BASE_URL

log = logging.getLogger(__name__)


class DataCenter(str, Enum):
    """
    Enum representing available data centers for network volumes.
    #TODO: Add more data centers as needed. Lock this to the available data center.
    """

    EU_RO_1 = "EU-RO-1"


class NetworkVolume(DeployableResource):
    """
    NetworkVolume resource for creating and managing Runpod network volumes.

    This class handles the creation, deployment, and management of network volumes
    that can be attached to serverless resources. Supports idempotent deployment
    where multiple volumes with the same name will reuse existing volumes.

    """

    # Internal fixed value
    dataCenterId: DataCenter = Field(default=DataCenter.EU_RO_1, frozen=True)

    id: Optional[str] = Field(default=None)
    name: Optional[str] = None
    size: Optional[int] = Field(default=50, gt=0)  # Size in GB

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.id}"

    @property
    def resource_id(self) -> str:
        """Unique resource ID based on name and datacenter for idempotent behavior."""
        if self.name:
            # Use name + datacenter for volumes with names to ensure idempotence
            resource_type = self.__class__.__name__
            config_key = f"{self.name}:{self.dataCenterId.value}"
            hash_obj = hashlib.md5(f"{resource_type}:{config_key}".encode())
            return f"{resource_type}_{hash_obj.hexdigest()}"
        else:
            # Fall back to default behavior for unnamed volumes
            return super().resource_id

    @field_serializer("dataCenterId")
    def serialize_data_center_id(self, value: Optional[DataCenter]) -> Optional[str]:
        """Convert DataCenter enum to string."""
        return value.value if value is not None else None

    @property
    def is_created(self) -> bool:
        "Returns True if the network volume already exists."
        return self.id is not None

    @property
    def url(self) -> str:
        """
        Returns the URL for the network volume resource.
        """
        if not self.id:
            raise ValueError("Network volume ID is not set")
        return f"{CONSOLE_BASE_URL}/user/storage"

    def is_deployed(self) -> bool:
        """
        Checks if the network volume resource is deployed and available.
        """
        return self.id is not None

    def _normalize_volumes_response(self, volumes_response) -> list:
        """Normalize API response to list format."""
        if isinstance(volumes_response, list):
            return volumes_response
        return volumes_response.get("networkVolumes", [])

    def _find_matching_volume(self, existing_volumes: list) -> Optional[dict]:
        """Find existing volume matching name and datacenter."""
        for volume_data in existing_volumes:
            if (
                volume_data.get("name") == self.name
                and volume_data.get("dataCenterId") == self.dataCenterId.value
            ):
                return volume_data
        return None

    async def _find_existing_volume(self, client) -> Optional["NetworkVolume"]:
        """Check for existing volume with same name and datacenter."""
        if not self.name:
            return None

        log.debug(f"Checking for existing network volume with name: {self.name}")
        volumes_response = await client.list_network_volumes()
        existing_volumes = self._normalize_volumes_response(volumes_response)

        if matching_volume := self._find_matching_volume(existing_volumes):
            log.info(
                f"Found existing network volume: {matching_volume.get('id')} with name '{self.name}'"
            )
            # Update our instance with the existing volume's ID
            self.id = matching_volume.get("id")
            return self

        return None

    async def _create_new_volume(self, client) -> "NetworkVolume":
        """Create a new network volume."""
        log.debug(f"Creating new network volume: {self.name or 'unnamed'}")
        payload = self.model_dump(exclude_none=True)
        result = await client.create_network_volume(payload)

        if volume := self.__class__(**result):
            return volume

        raise ValueError("Deployment failed, no volume was created.")

    async def deploy(self) -> "DeployableResource":
        """
        Deploys the network volume resource using the provided configuration.
        Returns a DeployableResource object.
        """
        try:
            # If the resource is already deployed, return it
            if self.is_deployed():
                log.debug(f"{self} exists")
                return self

            async with RunpodRestClient() as client:
                # Check for existing volume first
                if existing_volume := await self._find_existing_volume(client):
                    return existing_volume

                # No existing volume found, create a new one
                return await self._create_new_volume(client)

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise
