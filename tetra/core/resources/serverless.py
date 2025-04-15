from tetra.logger import get_logger
log = get_logger()

from typing import Dict, List, Optional
from enum import Enum
from urllib.parse import urljoin
from pydantic import field_validator
from . import runpod
from .base import DeployableResource
from .template import TemplateResource
from .gpu import GpuGroups


class ServerlessScalerType(Enum):
    QUEUE_DELAY = "QUEUE_DELAY"
    REQUEST_COUNT = "REQUEST_COUNT"


class ServerlessResource(DeployableResource):
    # Prevent mutation after creation
    model_config = {"frozen": True}

    # === Input Fields ===
    allowedCudaVersions: Optional[str] = ""
    env: Optional[Dict[str, str]] = None
    executionTimeoutMs: Optional[int] = 0
    gpuCount: Optional[int] = 1
    gpuIds: Optional[str] = GpuGroups.ADA_24.value
    idleTimeout: Optional[int] = 5
    locations: Optional[str] = None
    name: str
    networkVolumeId: Optional[str] = None
    scalerType: Optional[ServerlessScalerType] = ServerlessScalerType.QUEUE_DELAY
    scalerValue: Optional[int] = 4
    templateId: str
    workersMax: Optional[int] = 3
    workersMin: Optional[int] = 0
    workersPFBTarget: Optional[int] = None

    # === Runtime Fields ===
    activeBuildid: Optional[str] = None
    aiKey: Optional[str] = None
    computeType: Optional[str] = None
    createdAt: Optional[str] = None  # TODO: use datetime
    hubRelease: Optional[str] = None
    instanceIds: Optional[List[str]] = []
    repo: Optional[str] = None
    template: Optional[TemplateResource] = None
    userId: Optional[str] = None

    @property
    def url(self) -> str:
        if not self.id:
            raise ValueError("Missing self.id")
        return urljoin(runpod.endpoint_url_base, self.id)

    @field_validator("gpuIds")
    @classmethod
    def validate_gpu_ids(cls, value: str) -> str:
        """
        Validates and normalizes the comma-separated GPU IDs.
        Ensures each value is a valid GpuType or GpuGroup.
        """
        if value == "any":
            return ",".join(GpuGroups.list())

        ids = [v.strip() for v in value.split(",") if v.strip()]
        normalized = []

        for id_ in ids:
            # TODO: Check against GpuType
            # Check against GpuGroups
            if id_ in {g.value for g in GpuGroups}:
                normalized.append(id_)
            else:
                raise ValueError(f"Invalid GPU ID or group: '{id_}'")

        return ",".join(normalized)

    async def deploy(self) -> "ServerlessResource":
        """
        Deploys the serverless resource using the provided configuration.
        Returns a ServerlessResource object.
        """
        try:
            # If the resource is already deployed, return it
            if self.id:
                log.debug(f"Endpoint exists: {self.url}")
                return self

            result = runpod.create_endpoint(
                name=self.name,  # TODO: f"<project_name>-<name>-endpoint"
                template_id=self.templateId,
                gpu_ids=self.gpuIds,
                network_volume_id=self.networkVolumeId,
                locations=self.locations,
                idle_timeout=self.idleTimeout,
                scaler_type=self.scalerType.value,
                scaler_value=self.scalerValue,
                workers_min=self.workersMin,
                workers_max=self.workersMax,
                flashboot=True,  # TODO: self.flashboot
            )

            if endpoint := ServerlessResource(**result):
                log.debug(f"Endpoint deployed: {endpoint.url}")
                return endpoint

        except Exception as e:
            log.error(f"Endpoint failed to deploy: {e}")
            raise
