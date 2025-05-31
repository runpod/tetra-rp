import asyncio
from typing import Any, Dict, List, Optional
from enum import Enum
from urllib.parse import urljoin
from pydantic import field_validator, BaseModel, Field

from tetra_rp import get_logger
from tetra_rp.core.utils.backoff import get_backoff_delay

from .cloud import runpod
from .base import DeployableResource
from .template import TemplateResource
from .gpu import GpuGroups
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


log = get_logger("serverless")


CONSOLE_URL = "https://www.runpod.io/console/serverless/user/endpoint/%s"


class ServerlessScalerType(Enum):
    QUEUE_DELAY = "QUEUE_DELAY"
    REQUEST_COUNT = "REQUEST_COUNT"

    # Prevent mutation after creation
    model_config = {"frozen": True}


class ServerlessResource(DeployableResource):
    # === Input Fields ===
    allowedCudaVersions: Optional[str] = ""
    env: Optional[Dict[str, str]] = Field(default_factory=get_env_vars)
    executionTimeoutMs: Optional[int] = 0
    gpuCount: Optional[int] = 1
    gpuIds: Optional[str] = "any"
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
        Returns the RunPod endpoint object for this serverless resource.
        """
        if not self.id:
            raise ValueError("Missing self.id")
        return runpod.Endpoint(self.id)

    @field_validator("gpuIds")
    @classmethod
    def validate_gpu_ids(cls, value: str) -> str:
        """
        Validates and normalizes the comma-separated GPU IDs.
        Ensures each value is a valid GpuType or GpuGroup.
        """
        all_gpu_groups = GpuGroups.list()

        if value == "any":
            return ",".join(all_gpu_groups)

        ids = [v.strip() for v in value.split(",") if v.strip()]
        normalized = []

        for id_ in ids:
            # Check against GpuGroups
            if id_ in all_gpu_groups:
                normalized.append(id_)
                continue

            # Check against GpuType
            # try:
            #     if runpod.get_gpu(id_):
            #         normalized.append(id_)
            #         continue
            # except ValueError as e:
            #     log.error(f"`{id_}` {e}")
            #     # TODO: get all available GPU types and fuzzy match

        if not normalized:
            raise ValueError("Invalid gpuIds provided")

        return ",".join(normalized)

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

            if endpoint := self.__class__(**result):
                log.info(f"Deployed: {endpoint}")
                return endpoint

            raise ValueError("Deployment failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise

    async def run_sync(self, payload: Dict[str, Any]) -> object:
        """
        Executes a serverless endpoint request with the payload.
        Returns an object.
        """
        if not self.id:
            raise ValueError("Serverless is not deployed")

        log_group = f"{self}"
        log.info(f"{self.console_url} | API /run_sync")

        try:
            # log.debug(f"[{log_group}] Payload: {payload}")

            return await asyncio.to_thread(
                self.endpoint.run_sync, request_input=payload
            )

        except Exception as e:
            log.error(f"{log_group} | Exception: {e}")
            raise

    async def run(self, payload: Dict[str, Any]) -> "JobOutput":
        """
        Executes a serverless endpoint request with the payload.
        Returns a JobOutput object.
        """
        if not self.id:
            raise ValueError("Serverless is not deployed")

        log_group = f"{self}"
        log.info(f"{self.console_url} | API /run")

        try:
            # log.debug(f"[{log_group}] Payload: {payload}")

            job = await asyncio.to_thread(self.endpoint.run, request_input=payload)

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
                    log.debug(f"{log_group} | Status: {job_status}")
                else:
                    # Check worker status
                    job_status = health.workers.status.value
                    log.debug(f"{log_group} | Status: {job_status}")

                    if health.workers.status in [
                        Status.THROTTLED,
                        Status.UNHEALTHY,
                        Status.UNKNOWN,
                    ]:
                        log.debug(f"{log_group} | Health {health}")

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
                    job = JobOutput(**response)
                    log.info(f"{log_subgroup} | Delay Time: {job.delayTime} ms")
                    log.info(f"{log_subgroup} | Execution Time: {job.executionTime} ms")
                    return job

        except Exception as e:
            log.error(f"{log_group} | Exception: {e}")
            raise


class ServerlessEndpoint(ServerlessResource):
    """
    Represents a serverless endpoint distinct from a live serverless.
    Inherits from ServerlessResource.
    """

    pass


class JobOutput(BaseModel):
    id: str
    workerId: str
    status: str
    delayTime: int
    executionTime: int
    output: Optional[object] = None
    error: Optional[str] = ""


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
        if self.initializing > self.ready:
            return Status.INITIALIZING

        if self.throttled > self.ready:
            return Status.THROTTLED

        if self.unhealthy > self.ready:
            return Status.UNHEALTHY

        if self.ready or self.idle or self.running:
            return Status.READY

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
