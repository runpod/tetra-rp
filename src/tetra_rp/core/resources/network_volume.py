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
    NetworkVolume resource for creating and managing Runpod netowrk volumes.

    This class handles the creation, deployment, and management of network volumes
    that can be attached to serverless resources.

    """

    # Internal fixed value
    dataCenterId: DataCenter = Field(default=DataCenter.EU_RO_1, frozen=True)

    id: Optional[str] = Field(default=None)
    name: Optional[str] = None
    size: Optional[int] = Field(default=10, gt=0)  # Size in GB

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.id}"

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

    async def create_network_volume(self) -> str:
        """
        Creates a network volume using the provided configuration.
        Returns the volume ID.
        """
        async with RunpodRestClient() as client:
            # Create the network volume
            payload = self.model_dump(exclude_none=True)
            result = await client.create_network_volume(payload)

        if volume := self.__class__(**result):
            return volume

    def is_deployed(self) -> bool:
        """
        Checks if the network volume resource is deployed and available.
        """
        return self.id is not None

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

            # Create the network volume
            async with RunpodRestClient() as client:
                # Create the network volume
                payload = self.model_dump(exclude_none=True)
                result = await client.create_network_volume(payload)

            if volume := self.__class__(**result):
                return volume

            raise ValueError("Deployment failed, no volume was created.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise
