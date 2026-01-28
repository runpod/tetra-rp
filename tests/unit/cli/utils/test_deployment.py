"""Unit tests for CLI deployment utilities."""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

from tetra_rp.cli.utils.deployment import (
    deploy_to_environment,
    reconcile_and_provision_resources,
)


@pytest.fixture
def mock_flash_app():
    """Create a mock FlashApp instance."""
    app = AsyncMock()
    app.get_build_manifest = AsyncMock()
    app.update_build_manifest = AsyncMock()
    return app


@pytest.fixture
def mock_resource_manager():
    """Create a mock ResourceManager."""
    manager = MagicMock()
    manager.get_or_deploy_resource = AsyncMock()
    return manager


@pytest.fixture
def mock_deployed_resource():
    """Create a mock deployed resource."""
    resource = MagicMock()
    resource.endpoint_url = "https://example.com/endpoint"
    resource.endpoint_id = "endpoint-id-123"
    return resource


@pytest.mark.asyncio
async def test_deploy_to_environment_success(
    mock_flash_app, mock_deployed_resource, tmp_path
):
    """Test successful deployment flow with provisioning."""
    mock_flash_app.get_environment_by_name = AsyncMock()
    mock_flash_app.upload_build = AsyncMock(return_value={"id": "build-123"})
    mock_flash_app.deploy_build_to_environment = AsyncMock(
        return_value={"success": True}
    )
    mock_flash_app.get_build_manifest = AsyncMock(
        return_value={
            "resources": {
                "cpu": {"resource_type": "ServerlessResource"},
            }
        }
    )
    mock_flash_app.update_build_manifest = AsyncMock()

    build_path = Path("/tmp/build.tar.gz")
    local_manifest = {
        "resources": {
            "cpu": {"resource_type": "ServerlessResource"},
        },
        "resources_endpoints": {},
    }

    # Create temporary manifest file
    import json

    manifest_dir = tmp_path / ".flash"
    manifest_dir.mkdir()
    manifest_file = manifest_dir / "flash_manifest.json"
    manifest_file.write_text(json.dumps(local_manifest))

    with (
        patch("pathlib.Path.cwd", return_value=tmp_path),
        patch("tetra_rp.cli.utils.deployment.FlashApp.from_name") as mock_from_name,
        patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
        patch(
            "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
        ) as mock_create_resource,
    ):
        mock_from_name.return_value = mock_flash_app
        mock_manager = MagicMock()
        mock_manager.get_or_deploy_resource = AsyncMock(
            return_value=mock_deployed_resource
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.return_value = MagicMock()

        result = await deploy_to_environment("app-name", "dev", build_path)

        assert result == {"success": True}
        mock_flash_app.get_environment_by_name.assert_awaited_once_with("dev")
        mock_flash_app.upload_build.assert_awaited_once_with(build_path)
        mock_flash_app.deploy_build_to_environment.assert_awaited_once()


@pytest.mark.asyncio
async def test_deploy_to_environment_provisioning_failure(mock_flash_app, tmp_path):
    """Test deployment when provisioning fails."""
    mock_flash_app.get_environment_by_name = AsyncMock()
    mock_flash_app.upload_build = AsyncMock(return_value={"id": "build-123"})
    # State Manager has no resources, so local_manifest resources will be NEW
    mock_flash_app.get_build_manifest = AsyncMock(
        return_value={
            "resources": {},
        }
    )

    build_path = Path("/tmp/build.tar.gz")
    local_manifest = {
        "resources": {
            "cpu": {"resource_type": "ServerlessResource"},
        },
        "resources_endpoints": {},
    }

    # Create temporary manifest file
    import json

    manifest_dir = tmp_path / ".flash"
    manifest_dir.mkdir()
    manifest_file = manifest_dir / "flash_manifest.json"
    manifest_file.write_text(json.dumps(local_manifest))

    with (
        patch("pathlib.Path.cwd", return_value=tmp_path),
        patch("tetra_rp.cli.utils.deployment.FlashApp.from_name") as mock_from_name,
        patch("tetra_rp.cli.utils.deployment.ResourceManager") as mock_manager_cls,
        patch(
            "tetra_rp.cli.utils.deployment.create_resource_from_manifest"
        ) as mock_create_resource,
    ):
        mock_from_name.return_value = mock_flash_app
        mock_manager = MagicMock()
        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=Exception("Resource deployment failed")
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.return_value = MagicMock()

        with pytest.raises(RuntimeError) as exc_info:
            await deploy_to_environment("app-name", "dev", build_path)

        assert "Failed to provision resources" in str(exc_info.value)
        mock_flash_app.deploy_build_to_environment.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconciliation_reprovisions_resources_without_endpoints(tmp_path):
    """Test that resources without endpoints are re-provisioned.

    Scenario: Previous deployment failed, so resources exist in State Manager
    but have no endpoint_url. The reconciliation should detect missing endpoints
    and re-provision those resources.
    """
    import json

    flash_dir = tmp_path / ".flash"
    flash_dir.mkdir()

    # Local manifest has mothership + worker
    local_manifest = {
        "resources": {
            "mothership": {
                "is_mothership": True,
                "resource_type": "CpuLiveLoadBalancer",
            },
            "worker": {
                "is_mothership": False,
                "resource_type": "LiveServerless",
            },
        }
    }
    (flash_dir / "flash_manifest.json").write_text(json.dumps(local_manifest))

    # State Manager has same resources but NO endpoints (failed deployment)
    state_manifest = {
        "resources": {
            "mothership": {
                "is_mothership": True,
                "resource_type": "CpuLiveLoadBalancer",
            },
            "worker": {
                "is_mothership": False,
                "resource_type": "LiveServerless",
            },
        },
        "resources_endpoints": {},  # Empty - previous deployment failed
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
        # Both resources should be re-provisioned (marked as "update" action)
        mock_manager = MagicMock()

        mock_mothership = MagicMock()
        mock_mothership.endpoint_url = "https://mothership.api.runpod.ai"
        mock_mothership.endpoint_id = "abc123mothership"

        mock_worker = MagicMock()
        mock_worker.endpoint_url = "https://worker.api.runpod.ai"
        mock_worker.endpoint_id = "xyz789worker"

        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=[mock_mothership, mock_worker]
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.side_effect = [MagicMock(), MagicMock()]

        result = await reconcile_and_provision_resources(
            app, "build-123", "dev", local_manifest, show_progress=False
        )

    # Both resources should have been provisioned (re-provisioned actually)
    assert "mothership" in result
    assert "worker" in result
    assert result["mothership"] == "https://mothership.api.runpod.ai"
    assert result["worker"] == "https://worker.api.runpod.ai"

    # Verify both resources were provisioned (2 calls to get_or_deploy_resource)
    assert mock_manager.get_or_deploy_resource.call_count == 2

    # Verify manifest was updated with endpoints
    app.update_build_manifest.assert_awaited_once()
    call_args = app.update_build_manifest.call_args
    updated_manifest = call_args[0][1]
    assert "resources_endpoints" in updated_manifest
    assert len(updated_manifest["resources_endpoints"]) == 2
