"""
Unit tests for universal CPU disk sizing in ServerlessEndpoint.

Tests the new smart disk sizing capability that applies CPU sizing logic
universally across all endpoint types when CPU instances are detected.
"""

import pytest
from runpod_flash.core.resources.cpu import CpuInstanceType
from runpod_flash.core.resources.serverless import ServerlessEndpoint
from runpod_flash.core.resources.template import PodTemplate


class TestServerlessEndpointUniversalCpuDetection:
    """Test universal CPU detection on ServerlessEndpoint (GPU class)."""

    def test_gpu_endpoint_with_cpu_instances_auto_sizes(self):
        """GPU endpoint with CPU instances should auto-size disk."""
        endpoint = ServerlessEndpoint(
            name="mixed-endpoint",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU3G_2_8],  # 20GB limit
        )

        # Should auto-size from 64GB default to 20GB
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 20

    def test_gpu_endpoint_with_cpu_instances_minimum_limit(self):
        """Multiple CPU instances should use minimum disk limit."""
        endpoint = ServerlessEndpoint(
            name="multi-cpu-endpoint",
            imageName="my-app:latest",
            instanceIds=[
                CpuInstanceType.CPU3G_1_4,  # 10GB limit
                CpuInstanceType.CPU3G_2_8,  # 20GB limit
                CpuInstanceType.CPU3G_4_16,  # 40GB limit
            ],
        )

        # Should use minimum: 10GB
        assert endpoint.template.containerDiskInGb == 10

    def test_gpu_endpoint_custom_disk_within_cpu_limit_allowed(self):
        """Custom disk size within CPU limit should be allowed."""
        template = PodTemplate(
            name="custom",
            imageName="my-app:latest",
            containerDiskInGb=15,  # Within CPU3G_2_8 limit of 20GB
        )

        endpoint = ServerlessEndpoint(
            name="custom-disk",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_2_8],
        )

        # Should keep custom 15GB (within 20GB limit)
        assert endpoint.template.containerDiskInGb == 15

    def test_gpu_endpoint_custom_disk_exceeds_cpu_limit_fails(self):
        """Custom disk size exceeding CPU limit should fail."""
        template = PodTemplate(
            name="oversized",
            imageName="my-app:latest",
            containerDiskInGb=50,  # Exceeds CPU3G_1_4 limit of 10GB
        )

        with pytest.raises(ValueError, match="Container disk size.*exceeds"):
            ServerlessEndpoint(
                name="will-fail",
                template=template,
                instanceIds=[CpuInstanceType.CPU3G_1_4],
            )

    def test_gpu_endpoint_default_auto_sizes_for_small_cpu_instance(self):
        """Default 64GB should auto-size to CPU limit for small CPU instance."""
        endpoint = ServerlessEndpoint(
            name="auto-sized-small",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        # Should auto-size from default 64GB to 10GB limit
        assert endpoint.template.containerDiskInGb == 10

    def test_gpu_endpoint_without_cpu_instances_no_auto_sizing(self):
        """GPU endpoint without CPU instances keeps default 64GB."""
        endpoint = ServerlessEndpoint(
            name="gpu-only",
            imageName="my-app:latest",
            # No instanceIds specified
        )

        # Should keep default 64GB
        assert endpoint.template.containerDiskInGb == 64

    def test_gpu_endpoint_mixed_cpu_generations(self):
        """Mixed CPU generations should use minimum across all types."""
        endpoint = ServerlessEndpoint(
            name="mixed-generations",
            imageName="my-app:latest",
            instanceIds=[
                CpuInstanceType.CPU3G_1_4,  # 10GB
                CpuInstanceType.CPU3C_2_4,  # 20GB
                CpuInstanceType.CPU5C_1_2,  # 15GB
            ],
        )

        # Should use minimum: 10GB
        assert endpoint.template.containerDiskInGb == 10

    def test_gpu_endpoint_cpu5c_sizing(self):
        """CPU5C instances should use 15GB per vCPU multiplier."""
        endpoint = ServerlessEndpoint(
            name="cpu5c-endpoint",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU5C_4_8],  # 4 vCPU × 15GB = 60GB
        )

        assert endpoint.template.containerDiskInGb == 60

    def test_gpu_endpoint_cpu3c_sizing(self):
        """CPU3C instances should use 10GB per vCPU multiplier."""
        endpoint = ServerlessEndpoint(
            name="cpu3c-endpoint",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU3C_4_8],  # 4 vCPU × 10GB = 40GB
        )

        assert endpoint.template.containerDiskInGb == 40

    def test_instance_ids_clears_gpu_config(self):
        """When instanceIds is specified, GPU config is cleared."""
        endpoint = ServerlessEndpoint(
            name="cpu-with-cleared-gpu",
            imageName="my-app:latest",
            gpuIds="NVIDIA A40",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        # GPU config should be cleared when CPU instances are specified
        assert endpoint.gpus == []
        assert endpoint.gpuIds == ""
        assert endpoint.gpuCount == 0
        # CPU config should be set
        assert endpoint.instanceIds == [CpuInstanceType.CPU3G_1_4]

    def test_empty_instance_ids_no_auto_sizing(self):
        """Empty instanceIds list should not trigger auto-sizing."""
        endpoint = ServerlessEndpoint(
            name="gpu-only",
            imageName="my-app:latest",
            instanceIds=[],  # Empty list
        )

        # Should keep default 64GB
        assert endpoint.template.containerDiskInGb == 64


class TestServerlessEndpointAutoSizingEdgeCases:
    """Test edge cases for auto-sizing logic."""

    def test_explicit_default_disk_size_auto_sizes(self):
        """Explicitly setting disk to 64GB (default) should auto-size for CPU."""
        template = PodTemplate(
            name="explicit-default",
            imageName="my-app:latest",
            containerDiskInGb=64,  # Explicitly set to default
        )

        endpoint = ServerlessEndpoint(
            name="test-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_2_8],  # 20GB limit
        )

        # Should auto-size from 64 to 20
        assert endpoint.template.containerDiskInGb == 20

    def test_single_cpu_instance_sizing(self):
        """Single CPU instance should calculate its disk limit correctly."""
        endpoint = ServerlessEndpoint(
            name="single-cpu",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU3G_4_16],  # 40GB limit
        )

        assert endpoint.template.containerDiskInGb == 40

    def test_duplicate_instance_ids_uses_same_limit(self):
        """Duplicate CPU instances should still use correct limit."""
        endpoint = ServerlessEndpoint(
            name="duplicate-cpu",
            imageName="my-app:latest",
            instanceIds=[
                CpuInstanceType.CPU3G_2_8,
                CpuInstanceType.CPU3G_2_8,  # Same instance twice
            ],
        )

        # Should use limit of CPU3G_2_8: 20GB
        assert endpoint.template.containerDiskInGb == 20

    def test_zero_disk_size_preserved_when_within_limit(self):
        """Zero disk size should be preserved if within CPU limit."""
        # This is an edge case - zero disk size is unusual but technically valid
        template = PodTemplate(
            name="zero-disk",
            imageName="my-app:latest",
            containerDiskInGb=0,
        )

        endpoint = ServerlessEndpoint(
            name="zero-disk-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        # Should preserve 0 (within 10GB limit)
        assert endpoint.template.containerDiskInGb == 0

    def test_minimum_valid_cpu_disk_size(self):
        """Smallest CPU instance (CPU3G_1_4) has 10GB limit."""
        endpoint = ServerlessEndpoint(
            name="minimal",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # Smallest: 10GB
        )

        assert endpoint.template.containerDiskInGb == 10

    def test_maximum_valid_cpu_disk_size(self):
        """Largest CPU instance (CPU5C_8_16) has 120GB limit."""
        endpoint = ServerlessEndpoint(
            name="maximal",
            imageName="my-app:latest",
            instanceIds=[CpuInstanceType.CPU5C_8_16],  # Largest: 120GB
        )

        assert endpoint.template.containerDiskInGb == 120


class TestErrorMessagesForUniversalCpuDetection:
    """Test that error messages are clear and actionable."""

    def test_disk_size_exceeded_error_message_includes_limits(self):
        """Error message should show all instance limits."""
        template = PodTemplate(
            name="oversized",
            imageName="my-app:latest",
            containerDiskInGb=50,
        )

        with pytest.raises(ValueError) as exc_info:
            ServerlessEndpoint(
                name="test",
                template=template,
                instanceIds=[
                    CpuInstanceType.CPU3G_1_4,  # 10GB
                    CpuInstanceType.CPU3G_2_8,  # 20GB
                ],
            )

        error_msg = str(exc_info.value)
        assert "cpu3g-1-4: max 10GB" in error_msg
        assert "cpu3g-2-8: max 20GB" in error_msg
        assert "Maximum allowed: 10GB" in error_msg

    def test_custom_disk_exceeding_small_cpu_limit_fails_with_guidance(self):
        """Custom disk exceeding CPU limit should provide guidance."""
        template = PodTemplate(
            name="oversized",
            imageName="my-app:latest",
            containerDiskInGb=50,  # Exceeds CPU3G_1_4 limit of 10GB
        )

        with pytest.raises(ValueError) as exc_info:
            ServerlessEndpoint(
                name="test",
                template=template,
                instanceIds=[CpuInstanceType.CPU3G_1_4],
            )

        error_msg = str(exc_info.value)
        assert "Container disk size" in error_msg
        assert "CpuServerlessEndpoint" in error_msg or "CPU" in error_msg
