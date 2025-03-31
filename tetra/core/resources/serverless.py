from typing import Dict, List, Optional, Union
from enum import Enum

from . import runpod
from .base import DeployableResource
from .template import TemplateResource
from .gpu import GpuType, GpuGroups


class ServerlessScalerType(Enum):
    QUEUE_DELAY = "QUEUE_DELAY"
    REQUEST_COUNT = "REQUEST_COUNT"


class ServerlessResourceInput(DeployableResource):
    allowedCudaVersions: Optional[str] = ""
    env: Optional[Dict[str, str]] = None
    executionTimeoutMs: Optional[int] = 0
    gpuCount: Optional[int] = 1
    gpuIds: Optional[List[Union[GpuType, GpuGroups, str]]] = [GpuGroups.ADA_24]
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

    def get_gpu_ids_as_string(self) -> str:
        """
        Converts the gpuIds list into a comma-separated string.
        Supports GpuType, GpuGroups, and string types.
        """
        if not self.gpuIds:
            return ""
        return ",".join(
            gpu.id if isinstance(gpu, GpuType) else gpu.value if isinstance(gpu, GpuGroups) else gpu
            for gpu in self.gpuIds
        )

    def deploy(self) -> "ServerlessResource":
        """
        Deploys the serverless resource using the provided configuration.
        Returns a ServerlessResource object.
        """
        try:
            result = runpod.create_endpoint(
                name=self.name, # TODO: f"<project_name>-<name>-endpoint"
                template_id=self.templateId,
                gpu_ids=self.get_gpu_ids_as_string(),
                network_volume_id=self.networkVolumeId,
                locations=self.locations,
                idle_timeout=self.idleTimeout,
                scaler_type=self.scalerType.value,
                scaler_value=self.scalerValue,
                workers_min=self.workersMin,
                workers_max=self.workersMax,
                flashboot=True, # TODO: self.flashboot
            )

            if endpoint := ServerlessResource(**result):
                print(f"Endpoint created: {endpoint.url}")
                return endpoint

        except Exception as e:
            print(f"Failed to deploy RunPod endpoint: {e}")
            raise


class ServerlessResource(ServerlessResourceInput):
    activeBuildid: Optional[str] = None
    aiKey: Optional[str] = None
    computeType: Optional[str] = None
    createdAt: Optional[str] = None  # TODO: use datetime
    gpuIds: Optional[str] = None
    hubRelease: Optional[str] = None
    id: str
    instanceIds: Optional[List[str]] = []
    repo: Optional[str] = None
    template: Optional[TemplateResource] = None
    userId: Optional[str] = None

    @property
    def url(self) -> str:
        return f"{runpod.endpoint_url_base}/{self.id}"
