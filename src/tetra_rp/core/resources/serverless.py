import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from runpod.endpoint.runner import Job

from ..api.runpod import RunpodGraphQLClient
from ..utils.backoff import get_backoff_delay
from .base import DeployableResource
from .cloud import runpod
from .constants import CONSOLE_URL
from .cpu import CpuInstanceType
from .environment import EnvironmentVars
from .gpu import GpuGroup
from .network_volume import NetworkVolume
from .template import KeyValuePair, PodTemplate


# Environment variables are loaded from the .env file
def get_env_vars() -> Dict[str, str]:
    """
    Returns the environment variables from the .env file.
    {
        "KEY": "VALUE",
    }
    """
    env_vars = EnvironmentVars()
    return env_vars.get_env()


log = logging.getLogger(__name__)


class ServerlessScalerType(Enum):
    QUEUE_DELAY = "QUEUE_DELAY"
    REQUEST_COUNT = "REQUEST_COUNT"


class CudaVersion(Enum):
    V11_8 = "11.8"
    V12_0 = "12.0"
    V12_1 = "12.1"
    V12_2 = "12.2"
    V12_3 = "12.3"
    V12_4 = "12.4"
    V12_5 = "12.5"
    V12_6 = "12.6"
    V12_7 = "12.7"
    V12_8 = "12.8"


class ServerlessResource(DeployableResource):
    """
    Base class for GPU serverless resource
    """

    _input_only = {
        "id",
        "cudaVersions",
        "env",
        "gpus",
        "flashboot",
        "imageName",
        "networkVolume",
    }

    # === Input-only Fields ===
    cudaVersions: Optional[List[CudaVersion]] = []  # for allowedCudaVersions
    env: Optional[Dict[str, str]] = Field(default_factory=get_env_vars)
    flashboot: Optional[bool] = True
    gpus: Optional[List[GpuGroup]] = [GpuGroup.ANY]  # for gpuIds
    imageName: Optional[str] = ""  # for template.imageName

    networkVolume: Optional[NetworkVolume] = None

    # === Input Fields ===
    executionTimeoutMs: Optional[int] = None
    gpuCount: Optional[int] = 1
    idleTimeout: Optional[int] = 5
    instanceIds: Optional[List[CpuInstanceType]] = None
    locations: Optional[str] = None
    name: str
    networkVolumeId: Optional[str] = None
    scalerType: Optional[ServerlessScalerType] = ServerlessScalerType.QUEUE_DELAY
    scalerValue: Optional[int] = 4
    templateId: Optional[str] = None
    workersMax: Optional[int] = 3
    workersMin: Optional[int] = 0
    workersPFBTarget: Optional[int] = None

    # === Runtime Fields ===
    activeBuildid: Optional[str] = None
    aiKey: Optional[str] = None
    allowedCudaVersions: Optional[str] = None
    computeType: Optional[str] = None
    createdAt: Optional[str] = None  # TODO: use datetime
    gpuIds: Optional[str] = ""
    hubRelease: Optional[str] = None
    repo: Optional[str] = None
    template: Optional[PodTemplate] = None
    userId: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.id}"

    @property
    def url(self) -> str:
        if not self.id:
            raise ValueError("Missing self.id")
        return CONSOLE_URL % self.id

    @property
    def endpoint(self) -> runpod.Endpoint:
        """
        Returns the Runpod endpoint object for this serverless resource.
        """
        if not self.id:
            raise ValueError("Missing self.id")
        return runpod.Endpoint(self.id)

    @field_serializer("scalerType")
    def serialize_scaler_type(
        self, value: Optional[ServerlessScalerType]
    ) -> Optional[str]:
        """Convert ServerlessScalerType enum to string."""
        return value.value if value is not None else None

    @field_serializer("instanceIds")
    def serialize_instance_ids(self, value: List[CpuInstanceType]) -> List[str]:
        """Convert CpuInstanceType enums to strings."""
        return [item.value if hasattr(item, "value") else str(item) for item in value]

    @field_validator("gpus")
    @classmethod
    def validate_gpus(cls, value: List[GpuGroup]) -> List[GpuGroup]:
        """Expand ANY to all GPU groups"""
        if value == [GpuGroup.ANY]:
            return GpuGroup.all()
        return value

    @model_validator(mode="after")
    def sync_input_fields(self):
        """Sync between temporary inputs and exported fields"""
        if self.flashboot:
            self.name += "-fb"

        if self.networkVolume and self.networkVolume.is_created:
            # Volume already exists, use its ID
            self.networkVolumeId = self.networkVolume.id

        if self.instanceIds:
            return self._sync_input_fields_cpu()
        else:
            return self._sync_input_fields_gpu()

    def _sync_input_fields_gpu(self):
        # GPU-specific fields
        if self.gpus:
            # Convert gpus list to gpuIds string
            self.gpuIds = ",".join(gpu.value for gpu in self.gpus)
        elif self.gpuIds:
            # Convert gpuIds string to gpus list (from backend responses)
            gpu_values = [v.strip() for v in self.gpuIds.split(",") if v.strip()]
            self.gpus = [GpuGroup(value) for value in gpu_values]

        if self.cudaVersions:
            # Convert cudaVersions list to allowedCudaVersions string
            self.allowedCudaVersions = ",".join(v.value for v in self.cudaVersions)
        elif self.allowedCudaVersions:
            # Convert allowedCudaVersions string to cudaVersions list (from backend responses)
            version_values = [
                v.strip() for v in self.allowedCudaVersions.split(",") if v.strip()
            ]
            self.cudaVersions = [CudaVersion(value) for value in version_values]

        return self

    def _sync_input_fields_cpu(self):
        # Override GPU-specific fields for CPU
        self.gpuCount = 0
        self.allowedCudaVersions = ""
        self.gpuIds = ""

        return self

    async def _ensure_network_volume_deployed(self) -> None:
        """
        Ensures network volume is deployed and ready.
        Updates networkVolumeId with the deployed volume ID.
        """
        if self.networkVolumeId:
            return

        if not self.networkVolume:
            log.info(f"{self.name} requires a default network volume")
            self.networkVolume = NetworkVolume(name=f"{self.name}-volume")

        if deployedNetworkVolume := await self.networkVolume.deploy():
            self.networkVolumeId = deployedNetworkVolume.id

    def is_deployed(self) -> bool:
        """
        Checks if the serverless resource is deployed and available.
        """
        try:
            if not self.id:
                return False

            response = self.endpoint.health()
            return response is not None
        except Exception as e:
            log.error(f"Error checking {self}: {e}")
            return False

    async def deploy(self) -> "DeployableResource":
        """
        Deploys the serverless resource using the provided configuration.
        Returns a DeployableResource object.
        """
        try:
            # If the resource is already deployed, return it
            if self.is_deployed():
                log.debug(f"{self} exists")
                return self

            # NEW: Ensure network volume is deployed first
            await self._ensure_network_volume_deployed()

            async with RunpodGraphQLClient() as client:
                payload = self.model_dump(exclude=self._input_only, exclude_none=True)
                result = await client.create_endpoint(payload)

            if endpoint := self.__class__(**result):
                return endpoint

            raise ValueError("Deployment failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise

    async def is_ready_for_requests(self, give_up_threshold=10) -> bool:
        """
        Asynchronously checks if the serverless resource is ready to handle
        requests by polling its health endpoint.

        Args:
            give_up_threshold (int, optional): The maximum number of polling
            attempts before giving up and raising an error. Defaults to 10.

        Returns:
            bool: True if the serverless resource is ready for requests.

        Raises:
            ValueError: If the serverless resource is not deployed.
            RuntimeError: If the health status is THROTTLED, UNHEALTHY, or UNKNOWN
            after exceeding the give_up_threshold.
        """
        if not self.is_deployed():
            raise ValueError("Serverless is not deployed")

        log.debug(f"{self} | API /health")

        current_pace = 0
        attempt = 0

        # Poll for health status
        while True:
            await asyncio.sleep(current_pace)

            health = await asyncio.to_thread(self.endpoint.health)
            health = ServerlessHealth(**health)

            if health.is_ready:
                return True
            else:
                # nothing changed, increase the gap
                attempt += 1
                indicator = "." * (attempt // 2) if attempt % 2 == 0 else ""
                if indicator:
                    log.info(f"{self} | {indicator}")

                status = health.workers.status
                if status in [
                    Status.THROTTLED,
                    Status.UNHEALTHY,
                    Status.UNKNOWN,
                ]:
                    log.debug(f"{self} | Health {status.value}")

                    if attempt >= give_up_threshold:
                        # Give up
                        raise RuntimeError(f"Health {status.value}")

            # Adjust polling pace appropriately
            current_pace = get_backoff_delay(attempt)

    async def run_sync(self, payload: Dict[str, Any]) -> "JobOutput":
        """
        Executes a serverless endpoint request with the payload.
        Returns a JobOutput object.
        """
        if not self.id:
            raise ValueError("Serverless is not deployed")

        def _fetch_job():
            return self.endpoint.rp_client.post(
                f"{self.id}/runsync", payload, timeout=60
            )

        try:
            # log.debug(f"[{log_group}] Payload: {payload}")

            # Poll until requests can be sent
            await self.is_ready_for_requests()

            log.info(f"{self} | API /run_sync")
            response = await asyncio.to_thread(_fetch_job)
            return JobOutput(**response)

        except Exception as e:
            health = await asyncio.to_thread(self.endpoint.health)
            health = ServerlessHealth(**health)
            log.info(f"{self} | Health {health.workers.status}")
            log.error(f"{self} | Exception: {e}")
            raise

    async def run(self, payload: Dict[str, Any]) -> "JobOutput":
        """
        Executes a serverless endpoint async request with the payload.
        Returns a JobOutput object.
        """
        if not self.id:
            raise ValueError("Serverless is not deployed")

        job: Optional[Job] = None

        try:
            # log.debug(f"[{self}] Payload: {payload}")

            # Poll until requests can be sent
            await self.is_ready_for_requests()

            # Create a job using the endpoint
            log.info(f"{self} | API /run")
            job = await asyncio.to_thread(self.endpoint.run, request_input=payload)

            log_subgroup = f"Job:{job.job_id}"

            log.info(f"{self} | Started {log_subgroup}")

            current_pace = 0
            attempt = 0
            job_status = Status.UNKNOWN
            last_status = job_status

            # Poll for job status
            while True:
                await asyncio.sleep(current_pace)

                if await self.is_ready_for_requests():
                    # Check job status
                    job_status = await asyncio.to_thread(job.status)

                if last_status == job_status:
                    # nothing changed, increase the gap
                    attempt += 1
                    indicator = "." * (attempt // 2) if attempt % 2 == 0 else ""
                    if indicator:
                        log.info(f"{log_subgroup} | {indicator}")
                else:
                    # status changed, reset the gap
                    log.info(f"{log_subgroup} | Status: {job_status}")
                    attempt = 0

                last_status = job_status

                # Adjust polling pace appropriately
                current_pace = get_backoff_delay(attempt)

                if job_status in ("COMPLETED", "FAILED", "CANCELLED"):
                    response = await asyncio.to_thread(job._fetch_job)
                    return JobOutput(**response)

        except Exception as e:
            if job and job.job_id:
                log.info(f"{self} | Cancelling job {job.job_id}")
                await asyncio.to_thread(job.cancel)

            log.error(f"{self} | Exception: {e}")
            raise


class ServerlessEndpoint(ServerlessResource):
    """
    Represents a serverless endpoint distinct from a live serverless.
    Inherits from ServerlessResource.
    """

    @model_validator(mode="after")
    def set_serverless_template(self):
        if not any([self.imageName, self.template, self.templateId]):
            raise ValueError(
                "Either imageName, template, or templateId must be provided"
            )

        if not self.templateId and not self.template:
            self.template = PodTemplate(
                name=self.resource_id,
                imageName=self.imageName,
                env=KeyValuePair.from_dict(self.env or get_env_vars()),
            )

        elif self.template:
            self.template.name = f"{self.resource_id}__{self.template.resource_id}"
            if self.imageName:
                self.template.imageName = self.imageName
            if self.env:
                self.template.env = KeyValuePair.from_dict(self.env)

        return self


class CpuServerlessEndpoint(ServerlessEndpoint):
    """
    Convenience class for CPU serverless endpoint.
    Represents a CPU-only serverless endpoint distinct from a live serverless.
    Inherits from ServerlessEndpoint.
    """

    instanceIds: Optional[List[CpuInstanceType]] = [CpuInstanceType.CPU3G_2_8]


class JobOutput(BaseModel):
    id: str
    workerId: str
    status: str
    delayTime: int
    executionTime: int
    output: Optional[Any] = None
    error: Optional[str] = ""

    def model_post_init(self, __context):
        log_group = f"Worker:{self.workerId}"
        log.info(f"{log_group} | Delay Time: {self.delayTime} ms")
        log.info(f"{log_group} | Execution Time: {self.executionTime} ms")


class Status(str, Enum):
    READY = "READY"
    INITIALIZING = "INITIALIZING"
    THROTTLED = "THROTTLED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class WorkersHealth(BaseModel):
    idle: int
    initializing: int
    ready: int
    running: int
    throttled: int
    unhealthy: int

    @property
    def status(self) -> Status:
        if self.ready or self.idle or self.running:
            return Status.READY

        if self.initializing:
            return Status.INITIALIZING

        if self.throttled:
            return Status.THROTTLED

        if self.unhealthy:
            return Status.UNHEALTHY

        return Status.UNKNOWN


class JobsHealth(BaseModel):
    completed: int
    failed: int
    inProgress: int
    inQueue: int
    retried: int


class ServerlessHealth(BaseModel):
    workers: WorkersHealth
    jobs: JobsHealth

    @property
    def is_ready(self) -> bool:
        return self.workers.status == Status.READY
