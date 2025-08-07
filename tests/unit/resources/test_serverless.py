"""
Unit tests for ServerlessResource and related classes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from tetra_rp.core.resources.serverless import (
    ServerlessResource,
    ServerlessEndpoint,
    CpuServerlessEndpoint,
    ServerlessScalerType,
    CudaVersion,
    JobOutput,
    WorkersHealth,
    JobsHealth,
    ServerlessHealth,
    Status,
)
from tetra_rp.core.resources.gpu import GpuGroup
from tetra_rp.core.resources.cpu import CpuInstanceType
from tetra_rp.core.resources.network_volume import NetworkVolume


class TestServerlessResource:
    """Test ServerlessResource base class functionality."""

    @pytest.fixture
    def basic_serverless_config(self) -> Dict[str, Any]:
        """Basic serverless configuration for testing."""
        return {
            "name": "test-serverless",
            "gpuCount": 1,
            "workersMax": 3,
            "workersMin": 0,
        }

    @pytest.fixture
    def mock_runpod_client(self):
        """Mock RunpodGraphQLClient."""
        client = AsyncMock()
        client.create_endpoint = AsyncMock()
        return client

    def test_serverless_resource_initialization(self, basic_serverless_config):
        """Test basic initialization of ServerlessResource."""
        serverless = ServerlessResource(**basic_serverless_config)

        # Name gets "-fb" appended because flashboot defaults to True
        assert serverless.name == "test-serverless-fb"
        assert serverless.gpuCount == 1
        assert serverless.workersMax == 3
        assert serverless.workersMin == 0
        assert serverless.scalerType == ServerlessScalerType.QUEUE_DELAY
        assert serverless.scalerValue == 4
        assert serverless.flashboot is True

    def test_str_representation(self, basic_serverless_config):
        """Test string representation of ServerlessResource."""
        serverless = ServerlessResource(**basic_serverless_config)
        serverless.id = "test-id-123"

        assert str(serverless) == "ServerlessResource:test-id-123"

    def test_url_property_with_id(self, basic_serverless_config):
        """Test URL property when ID is set."""
        serverless = ServerlessResource(**basic_serverless_config)
        serverless.id = "test-id-123"

        assert "test-id-123" in serverless.url

    def test_url_property_without_id_raises_error(self, basic_serverless_config):
        """Test URL property raises error when ID is not set."""
        serverless = ServerlessResource(**basic_serverless_config)

        with pytest.raises(ValueError, match="Missing self.id"):
            _ = serverless.url

    def test_endpoint_property_with_id(self, basic_serverless_config):
        """Test endpoint property when ID is set."""
        serverless = ServerlessResource(**basic_serverless_config)
        serverless.id = "test-id-123"

        endpoint = serverless.endpoint
        assert endpoint is not None

    def test_endpoint_property_without_id_raises_error(self, basic_serverless_config):
        """Test endpoint property raises error when ID is not set."""
        serverless = ServerlessResource(**basic_serverless_config)

        with pytest.raises(ValueError, match="Missing self.id"):
            _ = serverless.endpoint


class TestServerlessResourceNetworkVolume:
    """Test network volume integration in ServerlessResource."""

    @pytest.fixture
    def serverless_with_volume(self):
        """ServerlessResource with a network volume."""
        volume = NetworkVolume(name="test-volume", size=50)
        return ServerlessResource(
            name="test-serverless",
            networkVolume=volume,
        )

    @pytest.fixture
    def mock_network_volume(self):
        """Mock NetworkVolume for testing."""
        volume = AsyncMock(spec=NetworkVolume)
        volume.deploy = AsyncMock()
        volume.is_created = False
        volume.id = None
        return volume

    def test_sync_input_fields_with_created_volume(self):
        """Test sync_input_fields sets networkVolumeId when volume is created."""
        volume = NetworkVolume(name="test-volume", size=50)
        volume.id = "vol-123"
        # Use the actual property that checks is_created
        with patch.object(
            type(volume), "is_created", new_callable=lambda: property(lambda self: True)
        ):
            serverless = ServerlessResource(
                name="test-serverless",
                networkVolume=volume,
            )

            # The model validator should have set the networkVolumeId
            assert serverless.networkVolumeId == "vol-123"

    @pytest.mark.asyncio
    async def test_ensure_network_volume_deployed_with_existing_id(self):
        """Test _ensure_network_volume_deployed returns early if networkVolumeId exists."""
        serverless = ServerlessResource(
            name="test-serverless",
            networkVolumeId="vol-existing-123",
        )

        await serverless._ensure_network_volume_deployed()

        # Should return early, no volume creation
        assert serverless.networkVolumeId == "vol-existing-123"

    @pytest.mark.asyncio
    async def test_ensure_network_volume_deployed_creates_default_volume(self):
        """Test _ensure_network_volume_deployed creates default volume when none provided."""
        serverless = ServerlessResource(name="test-serverless")

        with patch.object(NetworkVolume, "deploy") as mock_deploy:
            deployed_volume = NetworkVolume(name="test-serverless-fb-volume", size=50)
            deployed_volume.id = "vol-new-123"
            mock_deploy.return_value = deployed_volume

            await serverless._ensure_network_volume_deployed()

            assert serverless.networkVolumeId == "vol-new-123"
            assert serverless.networkVolume is not None
            # Name includes "-fb" suffix from flashboot
            assert serverless.networkVolume.name == "test-serverless-fb-volume"

    @pytest.mark.asyncio
    async def test_ensure_network_volume_deployed_uses_existing_volume(self):
        """Test _ensure_network_volume_deployed uses existing volume."""
        volume = NetworkVolume(name="existing-volume", size=50)
        serverless = ServerlessResource(
            name="test-serverless",
            networkVolume=volume,
        )

        with patch.object(NetworkVolume, "deploy") as mock_deploy:
            deployed_volume = NetworkVolume(name="existing-volume", size=50)
            deployed_volume.id = "vol-existing-456"
            mock_deploy.return_value = deployed_volume

            await serverless._ensure_network_volume_deployed()

            assert serverless.networkVolumeId == "vol-existing-456"
            mock_deploy.assert_called_once()


class TestServerlessResourceValidation:
    """Test field validation and serialization."""

    def test_scaler_type_serialization(self):
        """Test ServerlessScalerType enum serialization."""
        serverless = ServerlessResource(
            name="test",
            scalerType=ServerlessScalerType.REQUEST_COUNT,
        )

        # Test the field serializer
        serialized = serverless.model_dump()
        assert serialized["scalerType"] == "REQUEST_COUNT"

    def test_instance_ids_serialization(self):
        """Test CpuInstanceType serialization."""
        serverless = ServerlessResource(
            name="test",
            instanceIds=[CpuInstanceType.CPU3G_2_8, CpuInstanceType.CPU3G_4_16],
        )

        # Test the field serializer
        serialized = serverless.model_dump()
        assert "cpu3g-2-8" in serialized["instanceIds"]
        assert "cpu3g-4-16" in serialized["instanceIds"]

    def test_gpus_validation_with_any(self):
        """Test GPU validation expands ANY to all GPU groups."""
        serverless = ServerlessResource(
            name="test",
            gpus=[GpuGroup.ANY],
        )

        # The validator should expand ANY to all GPU groups
        assert serverless.gpus is not None
        assert len(serverless.gpus) > 1
        assert GpuGroup.ANY not in serverless.gpus

    def test_gpus_validation_with_specific_gpus(self):
        """Test GPU validation preserves specific GPU selections."""
        specific_gpus = [GpuGroup.AMPERE_48, GpuGroup.AMPERE_24]
        serverless = ServerlessResource(
            name="test",
            gpus=specific_gpus,
        )

        assert serverless.gpus == specific_gpus

    def test_flashboot_appends_to_name(self):
        """Test flashboot=True appends '-fb' to name."""
        serverless = ServerlessResource(
            name="test-serverless",
            flashboot=True,
        )

        assert serverless.name == "test-serverless-fb"

    def test_no_flashboot_keeps_name(self):
        """Test flashboot=False keeps original name."""
        serverless = ServerlessResource(
            name="test-serverless",
            flashboot=False,
        )

        assert serverless.name == "test-serverless"


class TestServerlessResourceSyncFields:
    """Test model validator sync_input_fields method."""

    def test_sync_input_fields_gpu_mode(self):
        """Test sync_input_fields in GPU mode."""
        serverless = ServerlessResource(
            name="test",
            gpus=[GpuGroup.AMPERE_48, GpuGroup.AMPERE_24],
            cudaVersions=[CudaVersion.V12_1, CudaVersion.V11_8],
        )

        # Check GPU fields are properly set
        assert serverless.gpuIds is not None
        assert "AMPERE_48" in serverless.gpuIds
        assert "AMPERE_24" in serverless.gpuIds
        assert serverless.allowedCudaVersions is not None
        assert "12.1" in serverless.allowedCudaVersions
        assert "11.8" in serverless.allowedCudaVersions

    def test_sync_input_fields_cpu_mode(self):
        """Test sync_input_fields in CPU mode."""
        serverless = ServerlessResource(
            name="test",
            instanceIds=[CpuInstanceType.CPU3G_2_8],
        )

        # Check CPU mode overrides GPU fields
        assert serverless.gpuCount == 0
        assert serverless.allowedCudaVersions == ""
        assert serverless.gpuIds == ""

    def test_reverse_sync_gpuids_to_gpus(self):
        """Test reverse sync from gpuIds string to gpus list."""
        serverless = ServerlessResource(
            name="test",
            gpuIds="AMPERE_48,AMPERE_24",
        )

        # Should convert gpuIds string back to gpus list
        assert serverless.gpus is not None
        assert GpuGroup.AMPERE_48 in serverless.gpus
        assert GpuGroup.AMPERE_24 in serverless.gpus

    def test_reverse_sync_cuda_versions(self):
        """Test reverse sync from allowedCudaVersions string to cudaVersions list."""
        serverless = ServerlessResource(
            name="test",
            allowedCudaVersions="12.1,11.8",
        )

        # Should convert allowedCudaVersions string back to cudaVersions list
        assert serverless.cudaVersions is not None
        assert CudaVersion.V12_1 in serverless.cudaVersions
        assert CudaVersion.V11_8 in serverless.cudaVersions


class TestJobOutput:
    """Test JobOutput model."""

    @pytest.fixture
    def job_output_data(self):
        """Sample job output data."""
        return {
            "id": "job-123",
            "workerId": "worker-456",
            "status": "COMPLETED",
            "delayTime": 1500,
            "executionTime": 3000,
            "output": {"result": "success"},
            "error": "",
        }

    def test_job_output_initialization(self, job_output_data):
        """Test JobOutput initialization."""
        job_output = JobOutput(**job_output_data)

        assert job_output.id == "job-123"
        assert job_output.workerId == "worker-456"
        assert job_output.status == "COMPLETED"
        assert job_output.delayTime == 1500
        assert job_output.executionTime == 3000
        assert job_output.output == {"result": "success"}
        assert job_output.error == ""

    def test_job_output_with_error(self):
        """Test JobOutput with error."""
        job_output = JobOutput(
            id="job-123",
            workerId="worker-456",
            status="FAILED",
            delayTime=1000,
            executionTime=500,
            error="Something went wrong",
        )

        assert job_output.status == "FAILED"
        assert job_output.error == "Something went wrong"
        assert job_output.output is None


class TestServerlessResourceDeployment:
    """Test deployment and execution workflows."""

    @pytest.fixture
    def mock_runpod_client(self):
        """Mock RunpodGraphQLClient."""
        client = AsyncMock()
        client.create_endpoint = AsyncMock()
        return client

    @pytest.fixture
    def deployment_response(self):
        """Mock deployment response from RunPod API."""
        return {
            "id": "endpoint-123",
            "name": "test-serverless-fb",
            "gpuIds": "RTX4090",
            "allowedCudaVersions": "12.1",
            "networkVolumeId": "vol-456",
        }

    def test_is_deployed_false_when_no_id(self):
        """Test is_deployed returns False when no ID is set."""
        serverless = ServerlessResource(name="test")

        assert serverless.is_deployed() is False

    @pytest.mark.asyncio
    async def test_deploy_already_deployed(self):
        """Test deploy returns early when already deployed."""
        serverless = ServerlessResource(name="test")
        serverless.id = "existing-123"

        with patch.object(ServerlessResource, "is_deployed", return_value=True):
            result = await serverless.deploy()

            assert result == serverless

    @pytest.mark.asyncio
    async def test_deploy_success_with_network_volume(
        self, mock_runpod_client, deployment_response
    ):
        """Test successful deployment with network volume integration."""
        serverless = ServerlessResource(
            name="test-serverless",
            gpus=[GpuGroup.AMPERE_48],
            cudaVersions=[CudaVersion.V12_1],
        )

        mock_runpod_client.create_endpoint.return_value = deployment_response

        with patch(
            "tetra_rp.core.resources.serverless.RunpodGraphQLClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__.return_value = None

            with patch.object(
                ServerlessResource, "_ensure_network_volume_deployed"
            ) as mock_ensure_volume:
                with patch.object(
                    ServerlessResource, "is_deployed", return_value=False
                ):
                    result = await serverless.deploy()

        # Should call network volume deployment
        mock_ensure_volume.assert_called_once()

        # Should call create_endpoint
        mock_runpod_client.create_endpoint.assert_called_once()

        # Should return new instance with deployment data
        assert result.id == "endpoint-123"
        # The returned object gets the name from the API response, which gets processed again
        # result is a DeployableResource, so we need to cast it
        assert hasattr(result, "name") and result.name == "test-serverless-fb-fb"

    @pytest.mark.asyncio
    async def test_deploy_failure_raises_exception(self, mock_runpod_client):
        """Test deployment failure raises exception."""
        serverless = ServerlessResource(name="test")

        mock_runpod_client.create_endpoint.side_effect = Exception("API Error")

        with patch(
            "tetra_rp.core.resources.serverless.RunpodGraphQLClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__.return_value = None

            with patch.object(ServerlessResource, "is_deployed", return_value=False):
                with pytest.raises(Exception, match="API Error"):
                    await serverless.deploy()

    @pytest.mark.asyncio
    async def test_run_sync_success(self):
        """Test run_sync successful execution."""
        serverless = ServerlessResource(name="test")
        serverless.id = "endpoint-123"

        mock_endpoint = MagicMock()
        mock_endpoint.rp_client.post.return_value = {
            "id": "job-123",
            "workerId": "worker-456",
            "status": "COMPLETED",
            "delayTime": 1000,
            "executionTime": 2000,
            "output": {"result": "success"},
        }

        payload = {"input": "test data"}

        with patch.object(
            type(serverless),
            "endpoint",
            new_callable=lambda: property(lambda self: mock_endpoint),
        ):
            result = await serverless.run_sync(payload)

        assert isinstance(result, JobOutput)
        assert result.id == "job-123"
        assert result.status == "COMPLETED"
        mock_endpoint.rp_client.post.assert_called_once_with(
            "endpoint-123/runsync", payload, timeout=60
        )

    @pytest.mark.asyncio
    async def test_run_sync_no_id_raises_error(self):
        """Test run_sync raises error when no ID is set."""
        serverless = ServerlessResource(name="test")

        with pytest.raises(ValueError, match="Serverless is not deployed"):
            await serverless.run_sync({"input": "test"})

    @pytest.mark.asyncio
    async def test_run_async_success(self):
        """Test run async execution success."""
        serverless = ServerlessResource(name="test")
        serverless.id = "endpoint-123"

        mock_job = MagicMock()
        mock_job.job_id = "job-123"
        mock_job.status.side_effect = ["IN_QUEUE", "IN_PROGRESS", "COMPLETED"]
        mock_job._fetch_job.return_value = {
            "id": "job-123",
            "workerId": "worker-456",
            "status": "COMPLETED",
            "delayTime": 1000,
            "executionTime": 2000,
            "output": {"result": "success"},
        }

        mock_endpoint = MagicMock()
        mock_endpoint.run.return_value = mock_job

        payload = {"input": "test data"}

        with patch.object(
            type(serverless),
            "endpoint",
            new_callable=lambda: property(lambda self: mock_endpoint),
        ):
            with patch("asyncio.sleep"):  # Mock sleep to speed up test
                result = await serverless.run(payload)

        assert isinstance(result, JobOutput)
        assert result.id == "job-123"
        assert result.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_run_async_failure_cancels_job(self):
        """Test run async cancels job on exception."""
        serverless = ServerlessResource(name="test")
        serverless.id = "endpoint-123"

        mock_job = MagicMock()
        mock_job.job_id = "job-123"
        mock_job.status.side_effect = Exception("Job failed")
        mock_job.cancel.return_value = None

        mock_endpoint = MagicMock()
        mock_endpoint.run.return_value = mock_job

        with patch.object(
            type(serverless),
            "endpoint",
            new_callable=lambda: property(lambda self: mock_endpoint),
        ):
            with pytest.raises(Exception, match="Job failed"):
                await serverless.run({"input": "test"})

        mock_job.cancel.assert_called_once()


class TestServerlessEndpoint:
    """Test ServerlessEndpoint class."""

    def test_serverless_endpoint_requires_image_template_or_id(self):
        """Test ServerlessEndpoint validation requires image, template, or templateId."""
        with pytest.raises(
            ValueError,
            match="Either imageName, template, or templateId must be provided",
        ):
            ServerlessEndpoint(name="test")

    def test_serverless_endpoint_with_image_name(self):
        """Test ServerlessEndpoint creates template from imageName."""
        endpoint = ServerlessEndpoint(
            name="test-endpoint",
            imageName="test/image:latest",
        )

        assert endpoint.template is not None
        assert endpoint.template.imageName == "test/image:latest"
        # Template name will be generated based on resource IDs
        assert endpoint.template.name is not None
        assert "ServerlessEndpoint" in endpoint.template.name
        assert "PodTemplate" in endpoint.template.name

    def test_serverless_endpoint_with_template_id(self):
        """Test ServerlessEndpoint works with templateId."""
        endpoint = ServerlessEndpoint(
            name="test-endpoint",
            templateId="template-123",
        )

        assert endpoint.templateId == "template-123"
        assert endpoint.template is None

    def test_serverless_endpoint_with_existing_template(self):
        """Test ServerlessEndpoint with existing template."""
        from tetra_rp.core.resources.template import PodTemplate

        template = PodTemplate(name="existing-template", imageName="test/image:v1")
        endpoint = ServerlessEndpoint(
            name="test-endpoint",
            template=template,
        )

        assert endpoint.template is not None
        # Template name will be generated with resource IDs
        assert endpoint.template.name is not None
        assert "ServerlessEndpoint" in endpoint.template.name
        assert "PodTemplate" in endpoint.template.name
        assert endpoint.template.imageName == "test/image:v1"

    def test_serverless_endpoint_template_env_override(self):
        """Test ServerlessEndpoint overrides template env vars."""
        from tetra_rp.core.resources.template import PodTemplate, KeyValuePair

        template = PodTemplate(
            name="existing-template",
            imageName="test/image:v1",
            env=[KeyValuePair(key="OLD_VAR", value="old_value")],
        )
        endpoint = ServerlessEndpoint(
            name="test-endpoint",
            template=template,
            env={"NEW_VAR": "new_value"},
        )

        # Check that template and env are properly set
        assert endpoint.template is not None
        assert endpoint.template.env is not None
        assert len(endpoint.template.env) == 1
        assert endpoint.template.env[0].key == "NEW_VAR"
        assert endpoint.template.env[0].value == "new_value"


class TestCpuServerlessEndpoint:
    """Test CpuServerlessEndpoint class."""

    def test_cpu_serverless_endpoint_defaults(self):
        """Test CpuServerlessEndpoint has CPU instance defaults."""
        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            imageName="test/cpu-image:latest",
        )

        assert endpoint.instanceIds == [CpuInstanceType.CPU3G_2_8]
        # Should trigger CPU mode in sync_input_fields
        assert endpoint.gpuCount == 0
        assert endpoint.allowedCudaVersions == ""
        assert endpoint.gpuIds == ""

    def test_cpu_serverless_endpoint_custom_instance_types(self):
        """Test CpuServerlessEndpoint with custom instance types."""
        # Use valid CPU instance types from the enum
        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            imageName="test/cpu-image:latest",
            instanceIds=[CpuInstanceType.CPU3G_4_16, CpuInstanceType.CPU3C_8_16],
        )

        assert endpoint.instanceIds is not None
        assert len(endpoint.instanceIds) == 2
        assert CpuInstanceType.CPU3G_4_16 in endpoint.instanceIds
        assert CpuInstanceType.CPU3C_8_16 in endpoint.instanceIds


class TestServerlessResourceEdgeCases:
    """Test edge cases and error scenarios."""

    def test_is_deployed_with_exception(self):
        """Test is_deployed handles endpoint exceptions."""
        serverless = ServerlessResource(name="test")
        serverless.id = "test-id-123"

        mock_endpoint = MagicMock()
        mock_endpoint.health.side_effect = Exception("Connection error")

        with patch.object(
            type(serverless),
            "endpoint",
            new_callable=lambda: property(lambda self: mock_endpoint),
        ):
            result = serverless.is_deployed()

            assert result is False

    def test_reverse_sync_from_backend_response(self):
        """Test reverse sync when receiving backend response with gpuIds."""
        # This tests the lines 173-176 which convert gpuIds back to gpus list
        serverless = ServerlessResource(
            name="test",
            gpuIds="AMPERE_48,AMPERE_24,INVALID_GPU",  # Include invalid GPU to test error handling
        )

        # Should have parsed valid GPUs and skipped invalid ones
        assert serverless.gpus is not None
        valid_gpus = [
            gpu
            for gpu in serverless.gpus
            if gpu in [GpuGroup.AMPERE_48, GpuGroup.AMPERE_24]
        ]
        assert len(valid_gpus) >= 2

    @pytest.mark.asyncio
    async def test_run_sync_with_exception_logs_health(self):
        """Test run_sync exception handling logs health status."""
        serverless = ServerlessResource(name="test")
        serverless.id = "endpoint-123"

        mock_endpoint = MagicMock()
        mock_endpoint.rp_client.post.side_effect = Exception("Request failed")
        mock_endpoint.health.return_value = {
            "workers": {
                "idle": 0,
                "initializing": 0,
                "ready": 0,
                "running": 0,
                "throttled": 1,
                "unhealthy": 0,
            },
            "jobs": {
                "completed": 0,
                "failed": 0,
                "inProgress": 0,
                "inQueue": 0,
                "retried": 0,
            },
        }

        with patch.object(
            type(serverless),
            "endpoint",
            new_callable=lambda: property(lambda self: mock_endpoint),
        ):
            with pytest.raises(Exception, match="Request failed"):
                await serverless.run_sync({"input": "test"})


class TestHealthModels:
    """Test health-related models."""

    def test_workers_health_status_ready(self):
        """Test WorkersHealth status when workers are ready."""
        health = WorkersHealth(
            idle=2,
            initializing=0,
            ready=1,
            running=1,
            throttled=0,
            unhealthy=0,
        )

        assert health.status == Status.READY

    def test_workers_health_status_initializing(self):
        """Test WorkersHealth status when workers are initializing."""
        health = WorkersHealth(
            idle=0,
            initializing=2,
            ready=0,
            running=0,
            throttled=0,
            unhealthy=0,
        )

        assert health.status == Status.INITIALIZING

    def test_workers_health_status_throttled(self):
        """Test WorkersHealth status when workers are throttled."""
        health = WorkersHealth(
            idle=0,
            initializing=0,
            ready=0,
            running=0,
            throttled=2,
            unhealthy=0,
        )

        assert health.status == Status.THROTTLED

    def test_workers_health_status_unhealthy(self):
        """Test WorkersHealth status when workers are unhealthy."""
        health = WorkersHealth(
            idle=0,
            initializing=0,
            ready=0,
            running=0,
            throttled=0,
            unhealthy=2,
        )

        assert health.status == Status.UNHEALTHY

    def test_workers_health_status_unknown(self):
        """Test WorkersHealth status when all workers are zero."""
        health = WorkersHealth(
            idle=0,
            initializing=0,
            ready=0,
            running=0,
            throttled=0,
            unhealthy=0,
        )

        assert health.status == Status.UNKNOWN

    def test_serverless_health_is_ready_true(self):
        """Test ServerlessHealth is_ready property when ready."""
        workers_health = WorkersHealth(
            idle=1, initializing=0, ready=1, running=0, throttled=0, unhealthy=0
        )
        jobs_health = JobsHealth(
            completed=5, failed=0, inProgress=1, inQueue=2, retried=0
        )

        health = ServerlessHealth(workers=workers_health, jobs=jobs_health)

        assert health.is_ready is True

    def test_serverless_health_is_ready_false(self):
        """Test ServerlessHealth is_ready property when not ready."""
        workers_health = WorkersHealth(
            idle=0, initializing=2, ready=0, running=0, throttled=0, unhealthy=0
        )
        jobs_health = JobsHealth(
            completed=5, failed=0, inProgress=1, inQueue=2, retried=0
        )

        health = ServerlessHealth(workers=workers_health, jobs=jobs_health)

        assert health.is_ready is False
