"""Integration tests for mothership auto-provisioning with manifest reconciliation."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tetra_rp.runtime.mothership_provisioner import (
    compute_resource_hash,
    get_manifest_directory,
    provision_children,
)
from tetra_rp.runtime.state_manager_client import StateManagerClient


class TestMothershipProvisioningFlow:
    """Integration tests for mothership provisioning workflow."""

    @pytest.mark.asyncio
    async def test_provision_children_first_boot(self):
        """Test provisioning on first boot (no persisted manifest).

        Scenario:
        - Mothership starts for the first time
        - No persisted manifest in State Manager
        - All resources in local manifest should be deployed as NEW
        """
        # Setup: Create local manifest
        local_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "gpu_v1",
                },
                "cpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "cpu_v1",
                },
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = None  # No persisted
        mock_state_client.update_resource_state = AsyncMock()

        # Mock ResourceManager
        mock_gpu_resource = MagicMock()
        mock_gpu_resource.endpoint_url = "https://gpu-worker.api.runpod.ai"
        mock_cpu_resource = MagicMock()
        mock_cpu_resource.endpoint_url = "https://cpu-worker.api.runpod.ai"

        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[mock_gpu_resource, mock_cpu_resource]
            )
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: Both resources deployed
            assert mock_manager.get_or_deploy_resource.call_count == 2
            assert mock_state_client.update_resource_state.call_count == 2

            # Verify: State Manager updated with deployment info
            calls = mock_state_client.update_resource_state.call_args_list
            assert calls[0][0][1] == "gpu_worker"  # resource_name
            assert calls[1][0][1] == "cpu_worker"

    @pytest.mark.asyncio
    async def test_provision_children_with_changes(self):
        """Test provisioning with changed resources.

        Scenario:
        - Mothership boots with updated manifest
        - Some resources have changed config (different hash)
        - Changed resources should be updated, unchanged skipped
        """
        gpu_old_data = {"resource_type": "ServerlessResource", "config": "gpu_v1"}
        gpu_new_data = {"resource_type": "ServerlessResource", "config": "gpu_v2"}
        cpu_data = {"resource_type": "ServerlessResource", "config": "cpu_v1"}

        gpu_old_hash = compute_resource_hash(gpu_old_data)
        cpu_hash = compute_resource_hash(cpu_data)

        local_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": gpu_new_data,  # Changed
                "cpu_worker": cpu_data,  # Unchanged
            },
        }

        persisted_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {
                    **gpu_old_data,
                    "config_hash": gpu_old_hash,
                },
                "cpu_worker": {
                    **cpu_data,
                    "config_hash": cpu_hash,
                },
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = persisted_manifest
        mock_state_client.update_resource_state = AsyncMock()

        # Mock ResourceManager - only called for changed resource
        mock_gpu_resource = MagicMock()
        mock_gpu_resource.endpoint_url = "https://gpu-worker.api.runpod.ai"

        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                return_value=mock_gpu_resource
            )
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: Only changed resource deployed
            assert mock_manager.get_or_deploy_resource.call_count == 1
            # Verify: State Manager updated only for changed resource
            assert mock_state_client.update_resource_state.call_count == 1
            assert (
                mock_state_client.update_resource_state.call_args_list[0][0][1]
                == "gpu_worker"
            )

    @pytest.mark.asyncio
    async def test_provision_children_with_removed_resources(self):
        """Test provisioning with removed resources.

        Scenario:
        - Manifest previously had 3 resources
        - Current manifest has only 2 resources
        - Removed resource should be undeployed and removed from State Manager
        """
        local_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "gpu_v1",
                },
            },
        }

        persisted_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config_hash": "abc123",
                },
                "old_worker": {
                    "resource_type": "ServerlessResource",
                    "config_hash": "def456",
                },
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = persisted_manifest
        mock_state_client.update_resource_state = AsyncMock()
        mock_state_client.remove_resource_state = AsyncMock()

        # Mock ResourceManager
        mock_gpu_resource = MagicMock()
        mock_gpu_resource.endpoint_url = "https://gpu-worker.api.runpod.ai"

        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                return_value=mock_gpu_resource
            )
            # find_resources_by_name returns list of tuples: (resource_id, resource)
            mock_manager.find_resources_by_name = MagicMock(
                return_value=[("resource-id-123", "old_worker")]
            )
            mock_manager.undeploy_resource = AsyncMock(return_value={"success": True})
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: Removed resource undeployed
            assert mock_manager.undeploy_resource.call_count == 1
            # Verify: State Manager updated to remove old resource
            assert mock_state_client.remove_resource_state.call_count == 1
            assert (
                mock_state_client.remove_resource_state.call_args_list[0][0][1]
                == "old_worker"
            )

    @pytest.mark.asyncio
    async def test_provision_children_skips_load_balancer_resources(self):
        """Test that LoadBalancer resources are skipped during provisioning.

        Scenario:
        - Manifest includes LoadBalancerSlsResource (the mothership itself)
        - Mothership should not deploy itself as a child
        """
        local_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "resource_type": "LoadBalancerSlsResource",
                    "config": "lb_v1",
                },
                "gpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "gpu_v1",
                },
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = None
        mock_state_client.update_resource_state = AsyncMock()

        # Mock ResourceManager
        mock_gpu_resource = MagicMock()
        mock_gpu_resource.endpoint_url = "https://gpu-worker.api.runpod.ai"

        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                return_value=mock_gpu_resource
            )
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: Only gpu_worker deployed, mothership skipped
            assert mock_manager.get_or_deploy_resource.call_count == 1
            # Verify: Only gpu_worker in State Manager
            assert mock_state_client.update_resource_state.call_count == 1
            assert (
                mock_state_client.update_resource_state.call_args_list[0][0][1]
                == "gpu_worker"
            )

    @pytest.mark.asyncio
    async def test_provision_children_handles_deployment_errors(self):
        """Test that deployment errors don't block other resources.

        Scenario:
        - gpu_worker deployment fails
        - cpu_worker deployment should still proceed
        - State Manager should be updated with error for gpu_worker
        """
        local_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "gpu_v1",
                },
                "cpu_worker": {
                    "resource_type": "ServerlessResource",
                    "config": "cpu_v1",
                },
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = None
        mock_state_client.update_resource_state = AsyncMock()

        # Mock ResourceManager - gpu_worker fails, cpu_worker succeeds
        mock_cpu_resource = MagicMock()
        mock_cpu_resource.endpoint_url = "https://cpu-worker.api.runpod.ai"

        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            # First call (gpu_worker) raises error, second call (cpu_worker) succeeds
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[
                    RuntimeError("GPU allocation failed"),
                    mock_cpu_resource,
                ]
            )
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                # Should not raise despite gpu_worker failure
                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: Both resources attempted
            assert mock_manager.get_or_deploy_resource.call_count == 2

            # Verify: State Manager updated for both (error for gpu, success for cpu)
            assert mock_state_client.update_resource_state.call_count == 2

            # Verify: Error recorded for gpu_worker
            gpu_call = mock_state_client.update_resource_state.call_args_list[0]
            assert gpu_call[0][1] == "gpu_worker"
            assert "error" in gpu_call[0][2]
            assert gpu_call[0][2]["status"] == "failed"

            # Verify: Success recorded for cpu_worker
            cpu_call = mock_state_client.update_resource_state.call_args_list[1]
            assert cpu_call[0][1] == "cpu_worker"
            assert cpu_call[0][2]["status"] == "deployed"

    @pytest.mark.asyncio
    async def test_manifest_directory_endpoint_after_provisioning(self):
        """Test /manifest endpoint returns correct directory after provisioning.

        Scenario:
        - After provisioning, /manifest endpoint queried
        - Should return mapping of all deployed resources
        """
        with patch(
            "tetra_rp.runtime.mothership_provisioner.ResourceManager"
        ) as mock_rm_class:
            mock_gpu_resource = MagicMock()
            mock_gpu_resource.endpoint_url = "https://gpu-worker.api.runpod.ai"

            mock_cpu_resource = MagicMock()
            mock_cpu_resource.endpoint_url = "https://cpu-worker.api.runpod.ai"

            resources = {
                "ServerlessResource:gpu_worker": mock_gpu_resource,
                "ServerlessResource:cpu_worker": mock_cpu_resource,
            }

            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = resources
            mock_rm_class.return_value = mock_manager

            # Execute
            directory = await get_manifest_directory()

            # Verify: Directory contains all resources
            assert len(directory) == 2
            assert directory["gpu_worker"] == "https://gpu-worker.api.runpod.ai"
            assert directory["cpu_worker"] == "https://cpu-worker.api.runpod.ai"

    @pytest.mark.asyncio
    async def test_idempotent_provisioning_on_second_boot(self):
        """Test that second boot is idempotent (skips unchanged resources).

        Scenario:
        - First boot: Deploy gpu_worker, cpu_worker
        - Second boot: Both resources unchanged (same hash)
        - Second boot should skip both (no deployments)
        """
        gpu_data = {"resource_type": "ServerlessResource", "config": "gpu_v1"}
        cpu_data = {"resource_type": "ServerlessResource", "config": "cpu_v1"}

        gpu_hash = compute_resource_hash(gpu_data)
        cpu_hash = compute_resource_hash(cpu_data)

        local_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": gpu_data,
                "cpu_worker": cpu_data,
            },
        }

        persisted_manifest = {
            "version": "1.0",
            "resources": {
                "gpu_worker": {**gpu_data, "config_hash": gpu_hash},
                "cpu_worker": {**cpu_data, "config_hash": cpu_hash},
            },
        }

        # Mock StateManagerClient
        mock_state_client = AsyncMock(spec=StateManagerClient)
        mock_state_client.get_persisted_manifest.return_value = persisted_manifest
        mock_state_client.update_resource_state = AsyncMock()

        # Mock ResourceManager - should not be called
        with (
            patch("tetra_rp.runtime.mothership_provisioner.load_manifest") as mock_load,
            patch(
                "tetra_rp.runtime.mothership_provisioner.ResourceManager"
            ) as mock_rm_class,
            patch.dict(
                "os.environ",
                {"RUNPOD_ENDPOINT_ID": "mothership-123"},
            ),
        ):
            mock_load.return_value = local_manifest

            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock()
            mock_rm_class.return_value = mock_manager

            # Execute
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "flash_manifest.json"
                mothership_url = "https://mothership-123.api.runpod.ai"

                await provision_children(
                    manifest_path, mothership_url, mock_state_client
                )

            # Verify: No deployments (all unchanged)
            assert mock_manager.get_or_deploy_resource.call_count == 0
            # Verify: State Manager not updated
            assert mock_state_client.update_resource_state.call_count == 0
