import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from enum import Enum
from urllib.parse import urljoin
from pydantic import (
    field_serializer,
    field_validator,
    model_validator,
    BaseModel,
    Field,
)

from runpod.endpoint.runner import Job

from ..api.runpod import RunpodGraphQLClient
from ..utils.backoff import get_backoff_delay

from .cloud import runpod
from .base import DeployableResource
from .template import PodTemplate
from .gpu import GpuGroup
from .cpu import CpuInstanceType
from .environment import EnvironmentVars


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


CONSOLE_BASE_URL = os.environ.get("CONSOLE_BASE_URL", "https://console.runpod.io")
CONSOLE_URL = f"{CONSOLE_BASE_URL}/serverless/user/endpoint/%s"


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

    _input_only = {"id", "cudaVersions", "env", "gpus", "flashboot"}

    # === Input-only Fields ===
    cudaVersions: Optional[List[CudaVersion]] = []  # for allowedCudaVersions
    env: Optional[Dict[str, str]] = Field(default_factory=get_env_vars)
    flashboot: Optional[bool] = True
    gpus: Optional[List[GpuGroup]] = [GpuGroup.ANY]  # for gpuIds

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
        return urljoin(runpod.endpoint_url_base, self.id)

    @property
    def console_url(self) -> str:
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

    def model_dump(self, **kwargs):
        """Override to exclude input-only fields from serialization"""
        return super().model_dump(
            exclude=self._input_only, exclude_none=True, by_alias=True, **kwargs
        )

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
            log.error(f"Error checking {self.console_url}: {e}")
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

            async with RunpodGraphQLClient() as client:
                payload = self.model_dump()
                result = await client.create_endpoint(payload)

            if endpoint := self.__class__(**result):
                log.info(f"Deployed: {endpoint}")
                return endpoint

            raise ValueError("Deployment failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise

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

        log_group = f"{self}"
        log.info(f"{self.console_url} | API /run_sync")

        try:
            # log.debug(f"[{log_group}] Payload: {payload}")

            response = await asyncio.to_thread(_fetch_job)
            return JobOutput(**response)

        except Exception as e:
            health = await asyncio.to_thread(self.endpoint.health)
            health = ServerlessHealth(**health)
            log.info(f"{log_group} | Health {health.workers.status}")

            log.error(f"{log_group} | Exception: {e}")
            raise

    async def run(self, payload: Dict[str, Any]) -> "JobOutput":
        """
        Executes a serverless endpoint async request with the payload.
        Returns a JobOutput object.
        """
        if not self.id:
            raise ValueError("Serverless is not deployed")

        log_group = f"{self}"
        log.info(f"{self.console_url} | API /run")

        try:
            # log.debug(f"[{log_group}] Payload: {payload}")

            job: Job = await asyncio.to_thread(self.endpoint.run, request_input=payload)

            log_subgroup = f"Job:{job.job_id}"

            log.info(f"{log_group} | Started {log_subgroup}")

            current_pace = 0
            attempt = 0
            job_status = Status.UNKNOWN
            last_status = job_status

            # Poll for job status
            while True:
                await asyncio.sleep(current_pace)

                # Check endpoint health
                health = await asyncio.to_thread(self.endpoint.health)
                health = ServerlessHealth(**health)

                if health.is_ready:
                    # Check job status
                    job_status = await asyncio.to_thread(job.status)

                else:
                    # Check worker status
                    job_status = health.workers.status.value

                    if health.workers.status in [
                        Status.THROTTLED,
                        Status.UNHEALTHY,
                        Status.UNKNOWN,
                    ]:

                        if attempt >= 10:
                            # Give up
                            log.info(f"{log_subgroup} | Cancelling")
                            await asyncio.to_thread(job.cancel)
                            raise RuntimeError(health.workers.status.value)

                # Adjust polling pace appropriately
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

                current_pace = get_backoff_delay(attempt)

                if job_status in ("COMPLETED", "FAILED", "CANCELLED"):
                    response = await asyncio.to_thread(job._fetch_job)
                    return JobOutput(**response)

        except Exception as e:
            log.error(f"{log_group} | Exception: {e}")
            raise


class ServerlessEndpoint(ServerlessResource):
    """
    Represents a serverless endpoint distinct from a live serverless.
    Inherits from ServerlessResource.
    """

    pass


class CpuServerlessEndpoint(ServerlessEndpoint):
    """
    Convenience class for CPU serverless endpoint.
    Represents a CPU-only serverless endpoint distinct from a live serverless.
    Inherits from ServerlessEndpoint.
    """

    def __init__(self, **data):
        if data.get("instanceIds", False):
            data["instanceIds"] = [CpuInstanceType.CPU5G_2_8]

        super().__init__(**data)


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
