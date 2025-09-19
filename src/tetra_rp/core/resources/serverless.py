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
from .environment import EnvironmentVars
from .gpu import GpuGroup
from .network_volume import NetworkVolume, DataCenter
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

    # Fields marked as _input_only are excluded from gql requests to make the client impl simpler
    _input_only = {
        "id",
        "cudaVersions",
        "datacenter",
        "env",
        "gpus",
        "flashboot",
        "imageName",
        "networkVolume",
        "resource_hash",
        "fields_to_update",
    }

    # hashed fields are fields that define configuration of an object. they are used for computing
    # if a resource has changed and should only be mutable fields from the perspective of the platform.
    # does not account for platform (Runpod) state fields (eg endpoint id) right now.
    _hashed_fields = {
            "datacenter",
            "env",
            "gpuIds",
            "networkVolume",
            "executionTimeoutMs",
            "gpuCount",
            "locations",
            "name",
            "networkVolumeId",
            "scalerType",
            "scalerValue",
            "workersMax",
            "workersMin",
            "workersPFBTarget",
            "allowedCudaVersions", 
    }

    # === Input-only Fields ===
    cudaVersions: Optional[List[CudaVersion]] = []  # for allowedCudaVersions
    env: Optional[Dict[str, str]] = Field(default_factory=get_env_vars)
    flashboot: Optional[bool] = True
    gpus: Optional[List[GpuGroup]] = [GpuGroup.ANY]  # for gpuIds
    imageName: Optional[str] = ""  # for template.imageName
    networkVolume: Optional[NetworkVolume] = None
    datacenter: DataCenter = Field(default=DataCenter.EU_RO_1)

    # === Input Fields ===
    executionTimeoutMs: Optional[int] = 0
    gpuCount: Optional[int] = 1
    idleTimeout: Optional[int] = 5
    locations: Optional[str] = None
    name: str
    networkVolumeId: Optional[str] = None
    scalerType: Optional[ServerlessScalerType] = ServerlessScalerType.QUEUE_DELAY
    scalerValue: Optional[int] = 4
    templateId: Optional[str] = None
    workersMax: Optional[int] = 3
    workersMin: Optional[int] = 0
    workersPFBTarget: Optional[int] = 0

    # === Runtime Fields ===
    activeBuildid: Optional[str] = None
    aiKey: Optional[str] = None
    allowedCudaVersions: str = ""
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
        if self.flashboot and not self.name.endswith("-fb"):
            self.name += "-fb"

        # Sync datacenter to locations field for API
        if not self.locations:
            self.locations = self.datacenter.value

        # Validate datacenter consistency between endpoint and network volume
        if self.networkVolume and self.networkVolume.dataCenterId != self.datacenter:
            raise ValueError(
                f"Network volume datacenter ({self.networkVolume.dataCenterId.value}) "
                f"must match endpoint datacenter ({self.datacenter.value})"
            )

        if self.networkVolume and self.networkVolume.is_created:
            # Volume already exists, use its ID
            self.networkVolumeId = self.networkVolume.id

        self._sync_input_fields_gpu()

        return self

    def _sync_input_fields_gpu(self):
        # GPU-specific fields
        # the response from the api for gpus is none
        # apply this path only if gpuIds is None, otherwise we overwrite gpuIds
        # with ANY gpu because the default for gpus is any
        if self.gpus and not self.gpuIds:
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

    async def _ensure_network_volume_deployed(self) -> None:
        """
        Ensures network volume is deployed and ready if one is specified.
        Updates networkVolumeId with the deployed volume ID.
        """
        if self.networkVolumeId:
            return

        if self.networkVolume:
            deployedNetworkVolume = await self.networkVolume.deploy()
            self.networkVolumeId = deployedNetworkVolume.id

    async def _sync_graphql_object_with_inputs(self, returned_endpoint: "ServerlessResource"):
        for _input_field in self._input_only:
            if _input_field not in ["resource_hash"] and getattr(self, _input_field) is not None:
                # sync input only fields stripped from gql request back to endpoint
                setattr(returned_endpoint, _input_field,  getattr(self, _input_field))

        # assigning template info back to the object is needed for updating it in the future
        returned_endpoint.template = self.template
        if returned_endpoint.template:
            returned_endpoint.template.id = returned_endpoint.templateId

        return returned_endpoint

    async def sync_config_with_deployed_resource(self, existing: "ServerlessResource") -> None:
        self.id = existing.id
        if not existing.template:
            raise ValueError("Existing resource does not have a template, this is an invalid state. Update resources and try again")
        self.template.id = existing.template.id

    async def _update_template(self) -> "DeployableResource":
        if not self.template:
            raise ValueError("Tried to update a template that doesn't exist. Redeploy endpoint or attach a template to it")

        try:
            async with RunpodGraphQLClient() as client:
                payload = self.template.model_dump(exclude={"resource_hash", "fields_to_update"}, exclude_none=True)
                result = await client.update_template(payload)
            if template := self.template.__class__(**result):
                return template 

            raise ValueError("Deployment failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to update: {e}")
            raise


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
                # some "input only" fields are specific to tetra and not used in gql
                exclude = {
                    f: ... for f in self._input_only} | {"template": {"resource_hash", "fields_to_update", "volumeInGb"} 
                 } # TODO: maybe include this as a class attr
                payload = self.model_dump(exclude=exclude, exclude_none=True)
                result = await client.create_endpoint(payload)

            # we need to merge the returned fields from gql with what the inputs are here
            if endpoint := self.__class__(**result):
                endpoint = await self._sync_graphql_object_with_inputs(endpoint)
                return endpoint 

            raise ValueError("Deployment failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to deploy: {e}")
            raise

    async def update(self) -> "DeployableResource":
        # check if we need to update the template
        # only update if the template exists already and there are fields to update for it
        if self.template and self.fields_to_update & set(self.template.model_fields):
            # we need to add the template id back here from hydrated state
            log.debug(f"loaded template to update: {self.template.model_dump()}")
            template = await self._update_template()
            self.template = template

            # if the only fields that need updated are template-only, just return now
            if self.fields_to_update ^ set(template.model_fields):
                log.debug("template-only update to endpoint complete")
                return self

        try:
            async with RunpodGraphQLClient() as client:
                exclude = {f: ... for f in self._input_only} | {"template": {"resource_hash"}} # TODO: maybe include this as a class attr
                # we need to include the id here so we update the existing endpoint
                del exclude["id"]
                payload = self.model_dump(exclude=exclude, exclude_none=True)
                result = await client.update_endpoint(payload)

            if endpoint := self.__class__(**result):
                # TODO: should we check that the returned id = the input?
                # we could "soft fail" and notify the user if we fall back to making a new endpoint
                endpoint = await self._sync_graphql_object_with_inputs(endpoint)
                return endpoint 

            raise ValueError("Update failed, no endpoint was returned.")

        except Exception as e:
            log.error(f"{self} failed to update: {e}")
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

        try:
            # log.debug(f"[{self}] Payload: {payload}")

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

    def _create_new_template(self) -> PodTemplate:
        """Create a new PodTemplate with standard configuration."""
        return PodTemplate(
            name=self.resource_id,
            imageName=self.imageName,
            env=KeyValuePair.from_dict(self.env or get_env_vars()),
        )

    def _configure_existing_template(self) -> None:
        """Configure an existing template with necessary overrides."""
        if self.template is None:
            return

        self.template.name = f"{self.resource_id}__{self.template.resource_id}"

        if self.imageName:
            self.template.imageName = self.imageName
        if self.env:
            self.template.env = KeyValuePair.from_dict(self.env)

    @model_validator(mode="after")
    def set_serverless_template(self):
        if not any([self.imageName, self.template, self.templateId]):
            raise ValueError(
                "Either imageName, template, or templateId must be provided"
            )

        if not self.templateId and not self.template:
            self.template = self._create_new_template()
        elif self.template:
            self._configure_existing_template()

        return self


class JobOutput(BaseModel):
    id: str
    workerId: str
    status: str
    delayTime: int
    executionTime: int
    output: Optional[Any] = None
    error: Optional[str] = ""

    def model_post_init(self, _: Any) -> None:
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
