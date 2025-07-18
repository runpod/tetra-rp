import logging
from enum import Enum
from typing import Optional

from pydantic import (
    Field,
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
    US_WA_1 = "US-WA-1"
    US_CA_1 = "US-CA-1"


class NetworkVolume(DeployableResource):
    """
    NetworkVolume resource for creating and managing Runpod netowrk volumes.

    This class handles the creation, deployment, and management of network volumes
    that can be attached to serverless resources.

    """

    dataCenterId: Optional[DataCenter] = None
    id: Optional[str] = Field(default=None)
    name: Optional[str] = None
    size: Optional[int] = None  # Size in GB

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
                log.debug(
                    f"Network volume {self.id} is already deployed. Mounting existing volume."
                )
                log.info(f"Mounted existing network volume: {self.id}")
                return self

            # Create the network volume
            self = await self.create_network_volume()

            if self.is_deployed():
                return self

            raise ValueError("Deployment failed, no volume was created.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise
