"""
Integration tests for CPU disk sizing across multiple components.

These tests verify that CPU disk sizing works correctly when different
components (ServerlessEndpoint, CpuServerlessEndpoint, LiveServerless variants)
interact with the CPU utilities and template system.
"""

import pytest
from tetra_rp.core.resources.cpu import CpuInstanceType
from tetra_rp.core.resources.serverless import ServerlessEndpoint
from tetra_rp.core.resources.serverless_cpu import CpuServerlessEndpoint
from tetra_rp.core.resources.live_serverless import LiveServerless, CpuLiveServerless
from tetra_rp.core.resources.template import PodTemplate


class TestCpuDiskSizingIntegration:
    """Test CPU disk sizing across different endpoint types."""

    def test_serverless_endpoint_no_auto_sizing(self):
        """Test ServerlessEndpoint (GPU) doesn't auto-size for CPU instances."""
        endpoint = ServerlessEndpoint(
            name="test-gpu-endpoint",
            imageName="test/gpu-image:latest",
        )

        # Should not have instanceIds, so no auto-sizing - uses default 64GB
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 64
        assert not hasattr(endpoint, "instanceIds")

    def test_cpu_serverless_endpoint_auto_sizing_flow(self):
        """Test complete CPU auto-sizing flow in CpuServerlessEndpoint."""
        endpoint = CpuServerlessEndpoint(
            name="test-cpu-endpoint",
            imageName="test/cpu-image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4, CpuInstanceType.CPU3G_2_8],
        )

        # Verify complete integration:
        # 1. CPU utilities calculate minimum disk size
        # 2. Template creation uses auto-sizing
        # 3. Validation passes
        assert endpoint.instanceIds == [
            CpuInstanceType.CPU3G_1_4,
            CpuInstanceType.CPU3G_2_8,
        ]
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 10  # Minimum of 10 and 20

    def test_live_serverless_cpu_integration(self):
        """Test CpuLiveServerless integrates CPU sizing with live serverless features."""
        live_serverless = CpuLiveServerless(
            name="test-cpu-live",
            instanceIds=[CpuInstanceType.CPU5C_1_2, CpuInstanceType.CPU5C_2_4],
        )

        # Verify integration:
        # 1. Uses CPU image (locked)
        # 2. CPU utilities calculate minimum disk size
        # 3. Template creation with auto-sizing
        # 4. Validation passes
        assert "tetra-rp-cpu:" in live_serverless.imageName
        assert live_serverless.instanceIds == [
            CpuInstanceType.CPU5C_1_2,
            CpuInstanceType.CPU5C_2_4,
        ]
        assert live_serverless.template is not None
        assert live_serverless.template.containerDiskInGb == 15  # Minimum of 15 and 30

    def test_template_integration_with_auto_sizing(self):
        """Test template creation and modification integrates with CPU sizing."""
        # Start with existing template at default size
        template = PodTemplate(name="base-template", imageName="test/image:v1")
        default_size = template.containerDiskInGb  # Should be 64GB default

        # Create CPU endpoint with the template
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        # Verify template was modified for CPU sizing
        assert endpoint.template.containerDiskInGb == 10
        assert endpoint.template.containerDiskInGb != default_size

    def test_template_integration_preserves_custom_size(self):
        """Test template integration preserves intentional custom sizing."""
        # Template with explicit custom size
        template = PodTemplate(
            name="custom-template",
            imageName="test/image:v1",
            containerDiskInGb=8,  # Explicit custom size
        )

        # Create CPU endpoint with the template
        endpoint = CpuServerlessEndpoint(
            name="test-endpoint",
            template=template,
            instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
        )

        # Verify custom size was preserved (within limits)
        assert endpoint.template.containerDiskInGb == 8

    def test_validation_integration_across_components(self):
        """Test disk size validation works across different endpoint types."""
        template_exceeding_limits = PodTemplate(
            name="large-template",
            imageName="test/image:v1",
            containerDiskInGb=200,  # Exceeds all CPU limits
        )

        # Should fail for CpuServerlessEndpoint
        with pytest.raises(ValueError, match="Container disk size 200GB exceeds"):
            CpuServerlessEndpoint(
                name="cpu-endpoint",
                template=template_exceeding_limits,
                instanceIds=[CpuInstanceType.CPU3G_1_4],
            )

        # Should fail for CpuLiveServerless
        with pytest.raises(ValueError, match="Container disk size 200GB exceeds"):
            CpuLiveServerless(
                name="cpu-live-endpoint",
                template=template_exceeding_limits,
                instanceIds=[CpuInstanceType.CPU3G_1_4],
            )

        # Should pass for regular ServerlessEndpoint (GPU)
        gpu_endpoint = ServerlessEndpoint(
            name="gpu-endpoint",
            template=template_exceeding_limits,
        )
        assert gpu_endpoint.template.containerDiskInGb == 200

    def test_mixed_cpu_generations_integration(self):
        """Test integration with mixed CPU instance generations."""
        # Mix CPU3G, CPU3C, and CPU5C instances
        mixed_instances = [
            CpuInstanceType.CPU3G_1_4,  # 10GB
            CpuInstanceType.CPU3C_2_4,  # 20GB
            CpuInstanceType.CPU5C_1_2,  # 15GB
        ]

        endpoint = CpuServerlessEndpoint(
            name="mixed-cpu-endpoint",
            imageName="test/image:latest",
            instanceIds=mixed_instances,
        )

        # Should use minimum across all generations
        assert endpoint.template is not None
        assert endpoint.template.containerDiskInGb == 10  # Minimum of 10, 20, 15

        # Verify validation would catch excessive sizes
        template_exceeding_min = PodTemplate(
            name="test",
            imageName="test/image:v1",
            containerDiskInGb=12,  # Exceeds minimum of 10GB
        )

        with pytest.raises(ValueError) as exc_info:
            CpuServerlessEndpoint(
                name="test-endpoint",
                template=template_exceeding_min,
                instanceIds=mixed_instances,
            )

        # Verify error message includes all instance types
        error_msg = str(exc_info.value)
        assert "cpu3g-1-4: max 10GB" in error_msg
        assert "cpu3c-2-4: max 20GB" in error_msg
        assert "cpu5c-1-2: max 15GB" in error_msg


class TestLiveServerlessImageLockingIntegration:
    """Test image locking integration in live serverless variants."""

    def test_live_serverless_image_consistency(self):
        """Test that LiveServerless variants maintain image consistency."""
        gpu_live = LiveServerless(name="gpu-live")
        cpu_live = CpuLiveServerless(name="cpu-live")

        # Verify different images are used
        assert gpu_live.imageName != cpu_live.imageName
        assert "tetra-rp:" in gpu_live.imageName
        assert "tetra-rp-cpu:" in cpu_live.imageName

        # Verify images remain locked despite attempts to change
        original_gpu_image = gpu_live.imageName
        original_cpu_image = cpu_live.imageName

        gpu_live.imageName = "custom/image:latest"
        cpu_live.imageName = "custom/image:latest"

        assert gpu_live.imageName == original_gpu_image
        assert cpu_live.imageName == original_cpu_image

    def test_live_serverless_template_integration(self):
        """Test live serverless template integration with disk sizing."""
        # GPU live serverless - no auto-sizing
        gpu_live = LiveServerless(name="gpu-live")
        assert gpu_live.template.containerDiskInGb == 64  # Default

        # CPU live serverless - auto-sizing enabled
        cpu_live = CpuLiveServerless(
            name="cpu-live",
            instanceIds=[CpuInstanceType.CPU3G_2_8],
        )
        assert cpu_live.template.containerDiskInGb == 20  # Auto-sized

    def test_live_serverless_validation_integration(self):
        """Test live serverless validation integrates with CPU limits."""
        # Custom template that exceeds CPU limits
        large_template = PodTemplate(
            name="large",
            imageName="will-be-overridden",
            containerDiskInGb=100,
        )

        # GPU live serverless should accept large template
        gpu_live = LiveServerless(
            name="gpu-live",
            template=large_template,
        )
        assert gpu_live.template.containerDiskInGb == 100

        # CPU live serverless should reject large template
        with pytest.raises(ValueError, match="Container disk size 100GB exceeds"):
            CpuLiveServerless(
                name="cpu-live",
                template=large_template,
                instanceIds=[CpuInstanceType.CPU3G_1_4],  # 10GB limit
            )
