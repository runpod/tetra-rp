"""Tests for drift detection in load balancer and CPU resources.

Ensures that configuration drift detection correctly identifies user-intended
changes while ignoring runtime-assigned fields and dynamic environment variables.
"""

import os

from tetra_rp.core.resources.cpu import CpuInstanceType
from tetra_rp.core.resources.load_balancer_sls_resource import (
    CpuLoadBalancerSlsResource,
    LoadBalancerSlsResource,
)
from tetra_rp.core.resources.serverless_cpu import CpuServerlessEndpoint

# Set a dummy API key for tests
os.environ.setdefault("RUNPOD_API_KEY", "test-key-for-unit-tests")


class TestLoadBalancerConfigHashStability:
    """Test that config_hash is stable and excludes runtime fields."""

    def test_lb_config_hash_unchanged_with_same_config(self):
        """Same configuration produces same hash."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )
        hash1 = lb1.config_hash

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )
        hash2 = lb2.config_hash

        assert hash1 == hash2, "Same config should produce same hash"

    def test_lb_config_hash_excludes_template_field(self):
        """Template object changes don't affect hash."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )
        hash1 = lb1.config_hash

        # Simulate API assigning a template
        from tetra_rp.core.resources.serverless import PodTemplate

        lb1.template = PodTemplate(imageName="test/image:latest", name="test")
        hash_after_template = lb1.config_hash

        assert hash1 == hash_after_template, "Template object should not affect hash"

    def test_lb_config_hash_excludes_template_id(self):
        """TemplateId assignment doesn't affect hash."""
        lb = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )
        hash1 = lb.config_hash

        # Simulate API assigning templateId
        lb.templateId = "template-abc-123"
        hash2 = lb.config_hash

        assert hash1 == hash2, "TemplateId assignment should not affect hash"

    def test_lb_config_hash_excludes_env_variables(self):
        """Environment variable changes don't trigger hash change."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            env={"VAR1": "value1"},
        )
        hash1 = lb1.config_hash

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            env={"VAR1": "value1", "VAR2": "value2"},
        )
        hash2 = lb2.config_hash

        assert hash1 == hash2, "Env variable changes should not affect hash"

    def test_lb_config_hash_excludes_api_assigned_fields(self):
        """Runtime fields (aiKey, userId, etc.) don't affect hash."""
        lb = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )
        hash1 = lb.config_hash

        # Simulate API assigning fields
        lb.aiKey = "key-123"
        lb.userId = "user-456"
        lb.createdAt = "2024-01-01T00:00:00Z"
        lb.activeBuildid = "build-789"

        hash2 = lb.config_hash

        assert hash1 == hash2, "API-assigned fields should not affect hash"

    def test_lb_config_hash_detects_image_change(self):
        """Image changes DO affect hash."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:v1",
        )
        hash1 = lb1.config_hash

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:v2",
        )
        hash2 = lb2.config_hash

        assert hash1 != hash2, "Image change should affect hash"


class TestCpuLoadBalancerConfigHashStability:
    """Test CPU load balancer config_hash behavior."""

    def test_cpu_lb_config_hash_excludes_gpu_fields(self):
        """GPU field values don't affect CPU load balancer hash."""
        cpu_lb1 = CpuLoadBalancerSlsResource(
            name="test-cpu-lb",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )
        hash1 = cpu_lb1.config_hash

        # Simulate API assigning GPU fields
        cpu_lb1.gpuCount = 4
        cpu_lb1.allowedCudaVersions = "12.0"
        cpu_lb1.gpuIds = "L40"

        hash2 = cpu_lb1.config_hash

        assert hash1 == hash2, "GPU fields should not affect CPU LB hash"

    def test_cpu_lb_config_hash_detects_instance_change(self):
        """CPU instance type changes DO affect hash."""
        cpu_lb1 = CpuLoadBalancerSlsResource(
            name="test-cpu-lb",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )
        hash1 = cpu_lb1.config_hash

        cpu_lb2 = CpuLoadBalancerSlsResource(
            name="test-cpu-lb",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_2_8],
        )
        hash2 = cpu_lb2.config_hash

        assert hash1 != hash2, "Instance type change should affect hash"

    def test_cpu_lb_config_hash_excludes_template(self):
        """Template assignment doesn't affect CPU LB hash."""
        cpu_lb = CpuLoadBalancerSlsResource(
            name="test-cpu-lb",
            imageName="test/image:latest",
        )
        hash1 = cpu_lb.config_hash

        from tetra_rp.core.resources.serverless import PodTemplate

        cpu_lb.template = PodTemplate(imageName="test/image:latest", name="test")
        hash2 = cpu_lb.config_hash

        assert hash1 == hash2, "Template assignment should not affect CPU LB hash"

    def test_cpu_lb_config_hash_consistency_with_serverless(self):
        """CPU LB and serverless endpoint hash consistently."""
        cpu_lb = CpuLoadBalancerSlsResource(
            name="test",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        cpu_serverless = CpuServerlessEndpoint(
            name="test",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        # Both should properly hash their configurations
        lb_hash = cpu_lb.config_hash
        serverless_hash = cpu_serverless.config_hash

        # Add runtime fields to both
        cpu_lb.template = None
        cpu_lb.aiKey = "key"
        cpu_serverless.template = None
        cpu_serverless.aiKey = "key"

        # Hashes should remain stable
        assert lb_hash == cpu_lb.config_hash
        assert serverless_hash == cpu_serverless.config_hash


class TestStructuralChangeDetection:
    """Test _has_structural_changes excludes runtime fields."""

    def test_structural_change_ignores_template_field(self):
        """Template changes are not structural."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
        )

        # Add template to lb1
        from tetra_rp.core.resources.serverless import PodTemplate

        lb1.template = PodTemplate(imageName="test/image:latest", name="test")

        # Should not detect structural changes
        assert not lb1._has_structural_changes(lb2), (
            "Template assignment should not be structural"
        )

    def test_structural_change_ignores_template_id(self):
        """TemplateId changes are not structural."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            templateId="abc-123",
        )

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            templateId="xyz-789",
        )

        # Should not detect structural changes
        assert not lb1._has_structural_changes(lb2), (
            "TemplateId change should not be structural"
        )

    def test_structural_change_detects_image_change(self):
        """Image changes ARE structural."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:v1",
        )

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:v2",
        )

        assert lb1._has_structural_changes(lb2), "Image change should be structural"

    def test_structural_change_detects_flashboot_change(self):
        """Flashboot toggle changes ARE structural."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            flashboot=True,
        )

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            flashboot=False,
        )

        assert lb1._has_structural_changes(lb2), "Flashboot change should be structural"

    def test_structural_change_detects_instance_change(self):
        """Instance type changes ARE structural."""
        cpu_lb1 = CpuLoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_1_4],
        )

        cpu_lb2 = CpuLoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            instanceIds=[CpuInstanceType.CPU3G_2_8],
        )

        assert cpu_lb1._has_structural_changes(cpu_lb2), (
            "Instance type change should be structural"
        )

    def test_structural_change_ignores_worker_change(self):
        """Worker scaling changes are NOT structural."""
        lb1 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            workersMin=1,
            workersMax=3,
        )

        lb2 = LoadBalancerSlsResource(
            name="test-lb",
            imageName="test/image:latest",
            workersMin=2,
            workersMax=5,
        )

        assert not lb1._has_structural_changes(lb2), (
            "Worker change should not be structural"
        )


class TestDriftDetectionRealWorldScenario:
    """Test realistic deployment scenarios."""

    def test_same_config_redeployed_no_drift(self):
        """Redeploying same config doesn't trigger drift."""
        config1 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1.0",
            workersMin=1,
            workersMax=5,
        )
        hash1 = config1.config_hash

        # Simulate second deployment with same config
        config2 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1.0",
            workersMin=1,
            workersMax=5,
        )
        hash2 = config2.config_hash

        assert hash1 == hash2, "Same config redeployed should have same hash"

    def test_env_var_changes_no_drift(self):
        """Environment variable changes don't trigger drift."""
        # First deployment with minimal env
        lb1 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1",
            env={"LOG_LEVEL": "INFO"},
        )
        hash1 = lb1.config_hash

        # Second deployment with additional env vars
        lb2 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1",
            env={
                "LOG_LEVEL": "INFO",
                "CUSTOM_VAR": "value",
                "ANOTHER": "config",
            },
        )
        hash2 = lb2.config_hash

        assert hash1 == hash2, "Env changes should not affect hash"

    def test_api_response_fields_no_drift(self):
        """API response fields don't trigger drift."""
        # First deployment (user config only)
        lb1 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1",
        )
        hash1 = lb1.config_hash

        # Simulate API response adding fields
        lb2 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1",
        )
        lb2.id = "endpoint-123"
        lb2.aiKey = "key-from-api"
        lb2.userId = "user-123"
        lb2.createdAt = "2024-01-15T10:00:00Z"
        lb2.activeBuildid = "build-456"

        hash2 = lb2.config_hash

        assert hash1 == hash2, "API-assigned fields should not trigger drift detection"

    def test_image_update_triggers_drift(self):
        """Image updates DO trigger drift detection."""
        lb1 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v1.0",
        )
        hash1 = lb1.config_hash

        lb2 = LoadBalancerSlsResource(
            name="api",
            imageName="myapp/api:v2.0",
        )
        hash2 = lb2.config_hash

        assert hash1 != hash2, "Image update should be detected as drift"
