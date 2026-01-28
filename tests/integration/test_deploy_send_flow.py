"""Integration tests for complete 'flash deploy send' workflow.

Tests the full end-to-end deployment flow including:
- Manifest reconciliation (NEW/CHANGED/UNCHANGED/REMOVED resources)
- Parallel resource provisioning
- State Manager persistence
- Local manifest updates
- Endpoint population and error handling
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tetra_rp.cli.utils.deployment import reconcile_and_provision_resources


@pytest.fixture
def temp_manifest_dir(tmp_path: Path) -> Path:
    """Create temporary directory with .flash subdirectory."""
    flash_dir = tmp_path / ".flash"
    flash_dir.mkdir()
    return flash_dir


@pytest.fixture
def sample_mothership_manifest() -> dict:
    """Local manifest with mothership and worker resources."""
    return {
        "version": "1.0",
        "resources": {
            "mothership": {
                "is_mothership": True,
                "resource_type": "CpuLiveLoadBalancer",
                "config": {"workersMin": 1, "workersMax": 3},
            },
            "worker": {
                "is_mothership": False,
                "resource_type": "LiveServerless",
                "config": {"workersMin": 0, "workersMax": 5},
            },
        },
    }


@pytest.fixture
def mock_deployed_mothership() -> MagicMock:
    """Mock deployed mothership resource."""
    resource = MagicMock()
    resource.endpoint_url = "https://mothership.api.runpod.ai/abcd1234"
    resource.endpoint_id = "mothership-ep-123"
    return resource


@pytest.fixture
def mock_deployed_worker() -> MagicMock:
    """Mock deployed worker resource."""
    resource = MagicMock()
    resource.endpoint_url = "https://worker.api.runpod.ai/wxyz5678"
    resource.endpoint_id = "worker-ep-456"
    return resource


class TestDeploySendFirstDeployment:
    """Tests for first deployment (all resources are NEW)."""

    @pytest.mark.asyncio
    async def test_first_deployment_all_resources_new(
        self,
        tmp_path,
        sample_mothership_manifest,
        mock_deployed_mothership,
        mock_deployed_worker,
    ):
        """First deployment with no State Manager manifest.

        Scenario:
        - No State Manager manifest exists (first deployment)
        - All resources in local manifest should be provisioned as NEW
        - Local manifest should be updated with endpoint URLs
        - State Manager should receive complete manifest
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(sample_mothership_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(
            return_value={}
        )  # First deployment, no state
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[mock_deployed_mothership, mock_deployed_worker]
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            result = await reconcile_and_provision_resources(
                app, "build-123", "dev", sample_mothership_manifest, show_progress=False
            )

        # Verify both resources provisioned
        assert len(result) == 2
        assert result["mothership"] == "https://mothership.api.runpod.ai/abcd1234"
        assert result["worker"] == "https://worker.api.runpod.ai/wxyz5678"

        # Verify both resources were deployed (2 calls)
        assert mock_manager.get_or_deploy_resource.call_count == 2

        # Verify State Manager was updated
        app.update_build_manifest.assert_awaited_once()
        call_args = app.update_build_manifest.call_args
        updated_manifest = call_args[0][1]
        assert "resources_endpoints" in updated_manifest
        assert updated_manifest["resources_endpoints"]["mothership"]
        assert updated_manifest["resources_endpoints"]["worker"]

        # Verify local manifest was written with endpoints
        manifest_data = json.loads(manifest_file.read_text())
        assert "resources_endpoints" in manifest_data
        assert manifest_data["resources_endpoints"]["mothership"]


class TestDeploySendWithChangedResources:
    """Tests for incremental deployment with config changes."""

    @pytest.mark.asyncio
    async def test_changed_resource_reprovisions(self, tmp_path, mock_deployed_worker):
        """Second deployment with changed resource config.

        Scenario:
        - Mothership resource exists with unchanged config
        - Worker resource has changed config (different workersMax)
        - Only worker should be re-provisioned
        - Mothership endpoint should be reused from State Manager
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()

        local_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "is_mothership": True,
                    "resource_type": "CpuLiveLoadBalancer",
                    "config": {"workersMin": 1, "workersMax": 3},
                },
                "worker": {
                    "is_mothership": False,
                    "resource_type": "LiveServerless",
                    "config": {"workersMin": 0, "workersMax": 10},  # Changed from 5
                },
            },
        }
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(local_manifest))

        state_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "is_mothership": True,
                    "resource_type": "CpuLiveLoadBalancer",
                    "config": {"workersMin": 1, "workersMax": 3},
                },
                "worker": {
                    "is_mothership": False,
                    "resource_type": "LiveServerless",
                    "config": {"workersMin": 0, "workersMax": 5},  # Old config
                },
            },
            "resources_endpoints": {
                "mothership": "https://mothership.api.runpod.ai/abcd1234",
                "worker": "https://worker.api.runpod.ai/old-endpoint",
            },
        }

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value=state_manifest)
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            # Only worker is re-provisioned (1 call, not 2)
            mock_manager.get_or_deploy_resource = AsyncMock(
                return_value=mock_deployed_worker
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.return_value = MagicMock()

            result = await reconcile_and_provision_resources(
                app, "build-123", "dev", local_manifest, show_progress=False
            )

        # Both endpoints should be present
        assert len(result) == 2
        assert "mothership" in result
        assert "worker" in result
        # Mothership endpoint should be reused from state
        assert result["mothership"] == "https://mothership.api.runpod.ai/abcd1234"
        # Worker endpoint should be new from provisioning
        assert result["worker"] == "https://worker.api.runpod.ai/wxyz5678"

        # Only worker should have been provisioned (1 call for "update")
        assert mock_manager.get_or_deploy_resource.call_count == 1

    @pytest.mark.asyncio
    async def test_missing_endpoint_triggers_reprovision(
        self, tmp_path, mock_deployed_mothership, mock_deployed_worker
    ):
        """Re-provision resource when endpoint is missing but config unchanged.

        Scenario:
        - Config unchanged but endpoint missing from State Manager
        - This can happen if a previous deployment failed after updating State Manager
        - Resource should be re-provisioned to get endpoint URL
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()

        local_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "is_mothership": True,
                    "resource_type": "CpuLiveLoadBalancer",
                    "config": {"workersMin": 1, "workersMax": 3},
                },
            },
        }
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(local_manifest))

        # State Manager has resource but NO endpoint
        state_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "is_mothership": True,
                    "resource_type": "CpuLiveLoadBalancer",
                    "config": {"workersMin": 1, "workersMax": 3},
                },
            },
            "resources_endpoints": {},  # Missing endpoint!
        }

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value=state_manifest)
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                return_value=mock_deployed_mothership
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.return_value = MagicMock()

            result = await reconcile_and_provision_resources(
                app, "build-123", "dev", local_manifest, show_progress=False
            )

        # Endpoint should be populated
        assert "mothership" in result
        assert result["mothership"] == "https://mothership.api.runpod.ai/abcd1234"

        # Resource should have been re-provisioned (1 "update" call)
        assert mock_manager.get_or_deploy_resource.call_count == 1


class TestDeploySendPartialFailure:
    """Tests for handling partial provisioning failures."""

    @pytest.mark.asyncio
    async def test_partial_provisioning_failure(
        self, tmp_path, sample_mothership_manifest, mock_deployed_mothership
    ):
        """One resource fails to provision, other succeeds.

        Scenario:
        - Mothership provisions successfully
        - Worker provision fails
        - Mothership endpoint should be saved
        - Error raised but mothership endpoints preserved
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(sample_mothership_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value={})
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            # Mothership succeeds, worker fails
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[
                    mock_deployed_mothership,
                    RuntimeError("Worker provisioning failed"),
                ]
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            with pytest.raises(RuntimeError) as exc_info:
                await reconcile_and_provision_resources(
                    app,
                    "build-123",
                    "dev",
                    sample_mothership_manifest,
                    show_progress=False,
                )

            assert "Worker provisioning failed" in str(exc_info.value)


class TestDeploySendMothershipeValidation:
    """Tests for mothership resource validation."""

    @pytest.mark.asyncio
    async def test_mothership_not_provisioned_raises_error(
        self, tmp_path, mock_deployed_worker
    ):
        """Error raised if mothership is defined but not provisioned.

        Scenario:
        - Manifest defines a mothership resource
        - Mothership provisioning fails or is skipped
        - Worker provisioning succeeds
        - Should raise RuntimeError about missing mothership
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()

        local_manifest = {
            "version": "1.0",
            "resources": {
                "mothership": {
                    "is_mothership": True,
                    "resource_type": "CpuLiveLoadBalancer",
                    "config": {"workersMin": 1, "workersMax": 3},
                },
                "worker": {
                    "is_mothership": False,
                    "resource_type": "LiveServerless",
                    "config": {"workersMin": 0, "workersMax": 5},
                },
            },
        }
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(local_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value={})
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            # Only worker is provisioned, mothership fails
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[
                    RuntimeError("Mothership provisioning failed"),
                    mock_deployed_worker,
                ]
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            with pytest.raises(RuntimeError):
                await reconcile_and_provision_resources(
                    app, "build-123", "dev", local_manifest, show_progress=False
                )


class TestDeploySendTimeout:
    """Tests for provisioning timeout behavior."""

    @pytest.mark.asyncio
    async def test_provisioning_timeout_raises_error(
        self, tmp_path, sample_mothership_manifest
    ):
        """Provisioning times out after 10 minutes.

        Scenario:
        - Provisioning takes > 600 seconds
        - asyncio.wait_for timeout triggers
        - Clear error message with RunPod dashboard reference
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(sample_mothership_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value={})
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
            patch("tetra_rp.cli.utils.deployment.asyncio.wait_for") as mock_wait_for,
        ):
            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock()
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            # Simulate timeout
            import asyncio

            mock_wait_for.side_effect = asyncio.TimeoutError()

            with pytest.raises(RuntimeError) as exc_info:
                await reconcile_and_provision_resources(
                    app,
                    "build-123",
                    "dev",
                    sample_mothership_manifest,
                    show_progress=False,
                )

            error_msg = str(exc_info.value)
            assert "timed out" in error_msg.lower()
            assert "RunPod" in error_msg


class TestDeploySendStateManagerPersistence:
    """Tests for State Manager interaction and persistence."""

    @pytest.mark.asyncio
    async def test_state_manager_updated_with_final_manifest(
        self,
        tmp_path,
        sample_mothership_manifest,
        mock_deployed_mothership,
        mock_deployed_worker,
    ):
        """State Manager receives complete updated manifest after provisioning.

        Scenario:
        - Local manifest uploaded to State Manager
        - Provisioning completes
        - State Manager manifest updated with all resource info and endpoints
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(sample_mothership_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(return_value={})
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[mock_deployed_mothership, mock_deployed_worker]
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            await reconcile_and_provision_resources(
                app, "build-123", "dev", sample_mothership_manifest, show_progress=False
            )

        # State Manager must be updated
        app.update_build_manifest.assert_awaited_once()
        call_args = app.update_build_manifest.call_args
        build_id_arg = call_args[0][0]
        manifest_arg = call_args[0][1]

        assert build_id_arg == "build-123"
        assert "resources" in manifest_arg
        assert "resources_endpoints" in manifest_arg
        assert len(manifest_arg["resources_endpoints"]) == 2

    @pytest.mark.asyncio
    async def test_state_manager_fetch_failure_handled(
        self,
        tmp_path,
        sample_mothership_manifest,
        mock_deployed_mothership,
        mock_deployed_worker,
    ):
        """Fetch failure from State Manager doesn't block first deployment.

        Scenario:
        - State Manager fetch raises exception
        - Should treat as "no previous manifest"
        - All resources provisioned as NEW
        """
        flash_dir = tmp_path / ".flash"
        flash_dir.mkdir()
        manifest_file = flash_dir / "flash_manifest.json"
        manifest_file.write_text(json.dumps(sample_mothership_manifest))

        app = AsyncMock()
        app.get_build_manifest = AsyncMock(
            side_effect=Exception("State Manager connection failed")
        )
        app.update_build_manifest = AsyncMock()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
            patch(
                "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
            ) as mock_create_resource,
        ):
            mock_manager = MagicMock()
            mock_manager.get_or_deploy_resource = AsyncMock(
                side_effect=[mock_deployed_mothership, mock_deployed_worker]
            )
            mock_manager_cls.return_value = mock_manager
            mock_create_resource.side_effect = [MagicMock(), MagicMock()]

            result = await reconcile_and_provision_resources(
                app, "build-123", "dev", sample_mothership_manifest, show_progress=False
            )

        # Should still succeed, treating as first deployment
        assert len(result) == 2
        # Both resources should be provisioned (no state manifest to compare)
        assert mock_manager.get_or_deploy_resource.call_count == 2
