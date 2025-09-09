"""
Unit tests for LoadBalancerSlsResource configuration and validation.

Tests the LoadBalancerSlsResource class that handles configuration for
Load Balancer serverless endpoints with dual HTTP/remote execution capabilities.
"""

import os
from unittest.mock import patch

from tetra_rp.core.resources.load_balancer_sls_resource import (
    LoadBalancerSlsResource,
    TETRA_IMAGE_TAG,
    TETRA_GPU_IMAGE,
    TETRA_CPU_IMAGE,
)


class TestLoadBalancerSlsResourceDefaults:
    """Test LoadBalancerSlsResource default configuration."""

    def test_default_image_tag(self):
        """Test default image tag from environment."""
        assert TETRA_IMAGE_TAG == "latest"

    def test_default_gpu_image(self):
        """Test default GPU image configuration."""
        expected = f"runpod/tetra-rp:{TETRA_IMAGE_TAG}"
        assert TETRA_GPU_IMAGE == expected

    def test_default_cpu_image(self):
        """Test default CPU image configuration."""
        expected = f"runpod/tetra-rp-cpu:{TETRA_IMAGE_TAG}"
        assert TETRA_CPU_IMAGE == expected

    @patch.dict(os.environ, {"TETRA_IMAGE_TAG": "v1.2.3"})
    def test_custom_image_tag(self):
        """Test custom image tag from environment."""
        # Need to reload the module to pick up new env var
        import importlib
        from tetra_rp.core.resources import load_balancer_sls_resource

        importlib.reload(load_balancer_sls_resource)

        assert load_balancer_sls_resource.TETRA_IMAGE_TAG == "v1.2.3"

    @patch.dict(os.environ, {"TETRA_GPU_IMAGE": "custom-gpu:latest"})
    def test_custom_gpu_image(self):
        """Test custom GPU image from environment."""
        import importlib
        from tetra_rp.core.resources import load_balancer_sls_resource

        importlib.reload(load_balancer_sls_resource)

        assert load_balancer_sls_resource.TETRA_GPU_IMAGE == "custom-gpu:latest"

    @patch.dict(os.environ, {"TETRA_CPU_IMAGE": "custom-cpu:latest"})
    def test_custom_cpu_image(self):
        """Test custom CPU image from environment."""
        import importlib
        from tetra_rp.core.resources import load_balancer_sls_resource

        importlib.reload(load_balancer_sls_resource)

        assert load_balancer_sls_resource.TETRA_CPU_IMAGE == "custom-cpu:latest"


class TestLoadBalancerSlsResourceConfiguration:
    """Test LoadBalancerSlsResource configuration and validation."""

    def test_basic_initialization(self):
        """Test basic LoadBalancerSlsResource initialization."""
        resource = LoadBalancerSlsResource(
            name="test-lb-resource", endpointId="test-endpoint-123"
        )

        assert resource.name == "test-lb-resource"
        assert resource.endpointId == "test-endpoint-123"
        assert resource.type == "LB"
        assert resource.imageName == TETRA_GPU_IMAGE

    def test_type_always_lb(self):
        """Test that type is always set to 'LB' regardless of input."""
        resource = LoadBalancerSlsResource(
            name="test-resource",
            endpointId="test-endpoint",
            type="SERVERLESS",  # This should be overridden
        )

        assert resource.type == "LB"

    def test_gpu_image_without_instance_ids(self):
        """Test GPU image selection when instanceIds is not provided."""
        resource = LoadBalancerSlsResource(
            name="test-resource", endpointId="test-endpoint"
        )

        assert resource.imageName == TETRA_GPU_IMAGE

    def test_cpu_image_with_instance_ids(self):
        """Test CPU image selection when instanceIds is provided."""
        resource = LoadBalancerSlsResource(
            name="test-resource",
            endpointId="test-endpoint",
            instanceIds=["cpu3g-1-4"],  # Use valid CPU instance type
        )

        assert resource.imageName == TETRA_CPU_IMAGE

    def test_cpu_image_with_empty_instance_ids(self):
        """Test GPU image selection when instanceIds is empty list."""
        resource = LoadBalancerSlsResource(
            name="test-resource", endpointId="test-endpoint", instanceIds=[]
        )

        # Empty list should be falsy, so should use GPU image
        assert resource.imageName == TETRA_GPU_IMAGE

    def test_image_name_property_override(self):
        """Test that imageName property always reflects instanceIds state."""
        # Create resource without instanceIds
        resource = LoadBalancerSlsResource(
            name="test-resource", endpointId="test-endpoint"
        )
        assert resource.imageName == TETRA_GPU_IMAGE

        # Dynamically add instanceIds (if possible)
        # Note: This tests the property behavior, though in practice
        # Pydantic models are typically immutable after creation
        if hasattr(resource, "__dict__"):
            resource.__dict__["instanceIds"] = ["cpu3g-1-4"]
            assert resource.imageName == TETRA_CPU_IMAGE

    def test_type_property_immutable(self):
        """Test that type property always returns 'LB'."""
        resource = LoadBalancerSlsResource(
            name="test-resource", endpointId="test-endpoint"
        )

        # Even if we try to change the underlying data, property should return LB
        assert resource.type == "LB"

        # Try to modify if possible (though Pydantic may prevent this)
        if hasattr(resource, "__dict__"):
            resource.__dict__["type"] = "DIFFERENT"
            assert resource.type == "LB"  # Property should still return LB


class TestLoadBalancerSlsResourceValidation:
    """Test LoadBalancerSlsResource validation logic."""

    def test_model_validator_sets_type(self):
        """Test that model validator sets type to LB."""
        # Test the validator directly
        data = {
            "name": "test-resource",
            "endpointId": "test-endpoint",
            "type": "SERVERLESS",  # Should be overridden
        }

        validated_data = LoadBalancerSlsResource.set_load_balancer_defaults(data)
        assert validated_data["type"] == "LB"

    def test_model_validator_sets_gpu_image_without_instance_ids(self):
        """Test validator sets GPU image when no instanceIds."""
        data = {"name": "test-resource", "endpointId": "test-endpoint"}

        validated_data = LoadBalancerSlsResource.set_load_balancer_defaults(data)
        assert validated_data["imageName"] == TETRA_GPU_IMAGE

    def test_model_validator_sets_cpu_image_with_instance_ids(self):
        """Test validator sets CPU image when instanceIds present."""
        data = {
            "name": "test-resource",
            "endpointId": "test-endpoint",
            "instanceIds": ["cpu3g-1-4"],
        }

        validated_data = LoadBalancerSlsResource.set_load_balancer_defaults(data)
        assert validated_data["imageName"] == TETRA_CPU_IMAGE

    def test_model_validator_preserves_other_fields(self):
        """Test validator preserves other fields unchanged."""
        data = {
            "name": "test-resource",
            "endpointId": "test-endpoint",
            "customField": "custom-value",
            "flashboot": False,
        }

        validated_data = LoadBalancerSlsResource.set_load_balancer_defaults(data)
        assert validated_data["customField"] == "custom-value"
        assert not validated_data["flashboot"]
        assert validated_data["name"] == "test-resource"
        assert validated_data["endpointId"] == "test-endpoint"

    def test_full_resource_creation_with_validation(self):
        """Test complete resource creation goes through validation."""
        resource = LoadBalancerSlsResource(
            name="full-test",
            endpointId="endpoint-123",
            env={"CUSTOM_VAR": "custom_value"},
            instanceIds=["cpu3g-1-4"],
            type="WRONG_TYPE",  # Should be overridden by validator
        )

        assert resource.type == "LB"
        assert resource.imageName == TETRA_CPU_IMAGE
        assert resource.name == "full-test"
        assert resource.endpointId == "endpoint-123"
        assert resource.env["CUSTOM_VAR"] == "custom_value"
        assert resource.instanceIds == ["cpu3g-1-4"]


class TestLoadBalancerSlsResourceInheritance:
    """Test LoadBalancerSlsResource inheritance from ServerlessResource."""

    def test_inherits_from_serverless_resource(self):
        """Test that LoadBalancerSlsResource inherits from ServerlessResource."""
        from tetra_rp.core.resources.serverless import ServerlessResource

        resource = LoadBalancerSlsResource(
            name="test-resource", endpointId="test-endpoint"
        )

        assert isinstance(resource, ServerlessResource)

    def test_serverless_resource_fields_available(self):
        """Test that ServerlessResource fields are available."""
        resource = LoadBalancerSlsResource(
            name="test-resource",
            endpointId="test-endpoint",
            env={"TEST_VAR": "test_value"},
            flashboot=False,
        )

        # These should be inherited from ServerlessResource
        assert resource.env["TEST_VAR"] == "test_value"
        assert not resource.flashboot

    def test_load_balancer_specific_behavior(self):
        """Test LoadBalancer-specific behavior vs base ServerlessResource."""
        # Create a LoadBalancerSlsResource
        lb_resource = LoadBalancerSlsResource(
            name="lb-resource", endpointId="lb-endpoint"
        )

        # LoadBalancer resource should have type LB
        assert lb_resource.type == "LB"

        # Should have the imageName property behavior
        assert lb_resource.imageName == TETRA_GPU_IMAGE
