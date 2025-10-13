"""
Unit tests for CpuServerlessEndpoint class.
"""

import pytest
from tetra_rp.core.resources.cpu import CpuInstanceType
from tetra_rp.core.resources.serverless_cpu import CpuServerlessEndpoint
from tetra_rp.core.resources.template import PodTemplate


class TestCpuServerlessEndpoint:
    """Test CpuServerlessEndpoint class behavior."""

    def test_cpu_serverless_endpoint_defaults(self):
        """Test CpuServerlessEndpoint has correct defaults."""
        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            imageName="test/cpu-image:latest",
        )

        # Should use default CPU3G_2_8 instance
        assert endpoint.instanceIds == [CpuInstanceType.CPU3G_2_8]
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 20

    def test_cpu_serverless_endpoint_custom_instances(self):
        """Test CpuServerlessEndpoint with custom instance types."""
        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            imageName="test/cpu-image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert endpoint.instanceIds == [CpuInstanceType.CPU3G_1_4]
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 10

    def test_cpu_serverless_endpoint_with_existing_template(self):
        """Test CpuServerlessEndpoint with existing template."""
        template = PodTemplate(name="existing", imageName="test/image:v1")

        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert endpoint.template.containerDiskInGb == 10  # Should be auto-sized

    def test_cpu_serverless_endpoint_preserves_custom_disk_size(self):
        """Test CpuServerlessEndpoint preserves custom disk size in template."""
        template = PodTemplate(
            name="existing",
            imageName="test/image:v1",
            containerDiskInGb=5,
        )

        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert endpoint.template.containerDiskInGb == 5  # Should preserve custom size

    def test_cpu_serverless_endpoint_with_template_id(self):
        """Test CpuServerlessEndpoint with templateId."""
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            templateId="template-123",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert endpoint.template is None
        assert endpoint.templateId == "template-123"


class TestCpuServerlessEndpointValidation:
    """Test CpuServerlessEndpoint disk size validation."""

    def test_validation_passes_within_limits(self):
        """Test validation passes when disk size is within limits."""
        template = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=5,
        )

        # Should not raise any exception
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        assert endpoint.template.containerDiskInGb == 5

    def test_validation_passes_at_exact_limit(self):
        """Test validation passes at exact disk size limit."""
        template = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=10,  # Exactly at limit
        )

        # Should not raise any exception
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        assert endpoint.template.containerDiskInGb == 10

    def test_validation_fails_exceeds_limits(self):
        """Test validation fails when disk size exceeds limits."""
        template = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=15,  # Exceeds 10GB limit
        )

        with pytest.raises(ValueError, match="Container disk size 15GB exceeds"):
            CpuServerlessEndpoint(
                name="test-endpoint",
                template=template,
                instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
            )

    def test_validation_fails_one_gb_over_limit(self):
        """Test validation fails when one GB over limit."""
        template = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=11,  # One GB over limit
        )

        with pytest.raises(ValueError, match="Container disk size 11GB exceeds"):
            CpuServerlessEndpoint(
                name="test-endpoint",
                template=template,
                instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
            )

    def test_validation_error_message_multiple_instances(self):
        """Test validation error message includes all instance limits."""
        template = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=25,
        )

        with pytest.raises(ValueError) as exc_info:
            CpuServerlessEndpoint(
                name="test-endpoint",
                template=template,
                instanceIds=[CpuInstanceType.CPU3G_1_4, CpuInstanceType.CPU3G_2_8],
            )

        error_msg = str(exc_info.value)
        assert "Container disk size 25GB exceeds" in error_msg
        assert "cpu3g-1-4: max 10GB" in error_msg
        assert "cpu3g-2-8: max 20GB" in error_msg
        assert "Maximum allowed: 10GB" in error_msg

    def test_no_validation_without_template(self):
        """Test no validation when using templateId instead of template."""
        # Should not raise any exception
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            templateId="template-123",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert endpoint.templateId == "template-123"

    def test_validation_mixed_instance_types_different_generations(self):
        """Test validation with mixed instance types from different generations."""
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            imageName="test/image:latest",
            instanceIds=[
                CpuInstanceType.CPU3G_1_4,  # 10GB
                CpuInstanceType.CPU3C_2_4,  # 20GB
                CpuInstanceType.CPU5C_1_2,  # 15GB
            ],
        )

        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 10  # Minimum across all types


class TestCpuEndpointMixin:
    """Test CpuEndpointMixin functionality."""

    def test_is_cpu_endpoint_detection(self):
        """Test _is_cpu_endpoint correctly identifies CPU endpoints."""
        cpu_endpoint = CpuServerlessEndpoint(
            name="cpu-endpoint",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        assert cpu_endpoint._is_cpu_endpoint() is True

    def test_is_cpu_endpoint_empty_instance_ids(self):
        """Test _is_cpu_endpoint with empty instanceIds."""
        cpu_endpoint = CpuServerlessEndpoint(
            name="cpu-endpoint",
            imageName="test/image:latest",
            instanceIds=[],
        )

        assert cpu_endpoint._is_cpu_endpoint() is False

    def test_get_cpu_container_disk_size(self):
        """Test _get_cpu_container_disk_size calculation."""
        cpu_endpoint = CpuServerlessEndpoint(
            name="cpu-endpoint",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4, CpuInstanceType.CPU3G_2_8],
        )

        assert cpu_endpoint._get_cpu_container_disk_size() == 10  # Minimum

    def test_sync_cpu_fields(self):
        """Test _sync_cpu_fields overrides GPU defaults."""
        cpu_endpoint = CpuServerlessEndpoint(
            name="cpu-endpoint",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        # GPU fields should be cleared/set to default CPU values
        assert cpu_endpoint.gpuCount == 0
        assert cpu_endpoint.allowedCudaVersions == ""
        assert cpu_endpoint.gpuIds == ""
