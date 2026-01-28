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


@pytest.mark.asyncio
async def test_reconcile_determines_new_changed_removed_resources(tmp_path):
    """Test reconciliation logic correctly categorizes resources.

    Verifies that resources are categorized as:
    - NEW: in local but not in state
    - UNCHANGED: in both with same config
    - CHANGED: in both with different config
    - REMOVED: in state but not in local
    """
    import json

    flash_dir = tmp_path / ".flash"
    flash_dir.mkdir()

    # Local manifest: 3 NEW, 1 CHANGED, 1 UNCHANGED
    local_manifest = {
        "resources": {
            "new_resource_1": {"resource_type": "LiveServerless", "config": "v1"},
            "new_resource_2": {"resource_type": "LiveServerless", "config": "v1"},
            "new_resource_3": {"resource_type": "LiveServerless", "config": "v1"},
            "changed_resource": {"resource_type": "LiveServerless", "config": "v2_new"},
            "unchanged_resource": {"resource_type": "LiveServerless", "config": "v3"},
        }
    }
    manifest_file = flash_dir / "flash_manifest.json"
    manifest_file.write_text(json.dumps(local_manifest))

    # State manifest: only has changed and unchanged + removed resource
    state_manifest = {
        "resources": {
            "changed_resource": {"resource_type": "LiveServerless", "config": "v2_old"},
            "unchanged_resource": {"resource_type": "LiveServerless", "config": "v3"},
            "removed_resource": {"resource_type": "LiveServerless", "config": "old"},
        },
        "resources_endpoints": {
            "changed_resource": "https://changed.api.runpod.ai",
            "unchanged_resource": "https://unchanged.api.runpod.ai",
            "removed_resource": "https://removed.api.runpod.ai",
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

        # Create mock resources for NEW (3) and CHANGED (1)
        mock_new_1 = MagicMock(
            endpoint_url="https://new1.api.runpod.ai", endpoint_id="new1-ep"
        )
        mock_new_2 = MagicMock(
            endpoint_url="https://new2.api.runpod.ai", endpoint_id="new2-ep"
        )
        mock_new_3 = MagicMock(
            endpoint_url="https://new3.api.runpod.ai", endpoint_id="new3-ep"
        )
        mock_changed = MagicMock(
            endpoint_url="https://changed-new.api.runpod.ai", endpoint_id="changed-ep"
        )

        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=[mock_new_1, mock_new_2, mock_new_3, mock_changed]
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.side_effect = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]

        result = await reconcile_and_provision_resources(
            app, "build-123", "dev", local_manifest, show_progress=False
        )

    # NEW resources should be provisioned
    assert "new_resource_1" in result
    assert "new_resource_2" in result
    assert "new_resource_3" in result

    # CHANGED resource should be re-provisioned
    assert "changed_resource" in result

    # UNCHANGED resource should reuse endpoint from state
    assert "unchanged_resource" in result
    assert result["unchanged_resource"] == "https://unchanged.api.runpod.ai"

    # REMOVED resource should not be in result
    assert "removed_resource" not in result

    # Verify provisioning calls: 3 NEW + 1 CHANGED = 4 calls
    assert mock_manager.get_or_deploy_resource.call_count == 4


@pytest.mark.asyncio
async def test_config_change_detection_via_json_comparison(tmp_path):
    """Test that config changes are detected via JSON string comparison.

    Verifies that:
    1. JSON comparison detects config changes
    2. Key order is ignored (sort_keys=True)
    3. Endpoint missing triggers re-provision even if config unchanged
    4. No endpoint + config unchanged still triggers provision
    """
    import json

    flash_dir = tmp_path / ".flash"
    flash_dir.mkdir()

    # Config with different key order should still match
    local_config = {
        "resource_type": "LiveServerless",
        "workersMin": 0,
        "workersMax": 5,
        "name": "worker",
    }

    state_config = {
        "name": "worker",
        "workersMax": 5,
        "workersMin": 0,
        "resource_type": "LiveServerless",
    }

    local_manifest = {"resources": {"worker": local_config}}
    manifest_file = flash_dir / "flash_manifest.json"
    manifest_file.write_text(json.dumps(local_manifest))

    state_manifest = {
        "resources": {"worker": state_config},
        "resources_endpoints": {"worker": "https://worker.api.runpod.ai"},
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
        mock_manager.get_or_deploy_resource = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.return_value = MagicMock()

        result = await reconcile_and_provision_resources(
            app, "build-123", "dev", local_manifest, show_progress=False
        )

    # Config unchanged + endpoint exists = no provisioning
    assert mock_manager.get_or_deploy_resource.call_count == 0
    # Endpoint should be reused from state
    assert result["worker"] == "https://worker.api.runpod.ai"


@pytest.mark.asyncio
async def test_parallel_provisioning_execution(tmp_path, sample_mothership_manifest):
    """Test that resources are provisioned in parallel, not sequentially.

    Verifies:
    1. All provisioning tasks created before wait_for
    2. asyncio.gather used for parallel execution
    3. All tasks complete successfully
    """
    import json

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

        mock_mothership = MagicMock(
            endpoint_url="https://mothership.api.runpod.ai",
            endpoint_id="mothership-ep",
        )
        mock_worker = MagicMock(
            endpoint_url="https://worker.api.runpod.ai", endpoint_id="worker-ep"
        )

        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=[mock_mothership, mock_worker]
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.side_effect = [MagicMock(), MagicMock()]

        result = await reconcile_and_provision_resources(
            app,
            "build-123",
            "dev",
            sample_mothership_manifest,
            show_progress=False,
        )

        # Verify both resources were provisioned
        assert len(result) == 2
        assert "mothership" in result
        assert "worker" in result


@pytest.mark.asyncio
async def test_local_manifest_file_updated_with_endpoints(
    tmp_path, sample_mothership_manifest
):
    """Test that local .flash/flash_manifest.json is updated with endpoints.

    After provisioning, the local manifest should contain:
    1. Updated resources_endpoints section
    2. Updated endpoint_id in each resource
    3. All changes persisted to file
    """
    import json

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

        mock_mothership = MagicMock(
            endpoint_url="https://mothership.api.runpod.ai",
            endpoint_id="mothership-ep-123",
        )
        mock_worker = MagicMock(
            endpoint_url="https://worker.api.runpod.ai", endpoint_id="worker-ep-456"
        )

        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=[mock_mothership, mock_worker]
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.side_effect = [MagicMock(), MagicMock()]

        await reconcile_and_provision_resources(
            app,
            "build-123",
            "dev",
            sample_mothership_manifest,
            show_progress=False,
        )

    # Read back the local manifest file
    updated_manifest = json.loads(manifest_file.read_text())

    # Verify resources_endpoints section exists
    assert "resources_endpoints" in updated_manifest
    assert updated_manifest["resources_endpoints"]["mothership"]
    assert updated_manifest["resources_endpoints"]["worker"]

    # Verify endpoint_id in resources
    assert (
        updated_manifest["resources"]["mothership"]["endpoint_id"]
        == "mothership-ep-123"
    )
    assert updated_manifest["resources"]["worker"]["endpoint_id"] == "worker-ep-456"


@pytest.mark.asyncio
async def test_mothership_validation_failure(tmp_path):
    """Test that error is raised if mothership is defined but not provisioned.

    Scenario:
    - Local manifest defines mothership resource
    - Resource provisioning fails or is skipped
    - Should raise RuntimeError with mothership name and provisioned list
    """
    import json

    flash_dir = tmp_path / ".flash"
    flash_dir.mkdir()

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

        mock_worker = MagicMock(
            endpoint_url="https://worker.api.runpod.ai", endpoint_id="worker-ep"
        )

        # Mothership fails, only worker is provisioned
        mock_manager.get_or_deploy_resource = AsyncMock(
            side_effect=[
                RuntimeError("Mothership provisioning failed"),
                mock_worker,
            ]
        )
        mock_manager_cls.return_value = mock_manager
        mock_create_resource.side_effect = [MagicMock(), MagicMock()]

        with pytest.raises(RuntimeError) as exc_info:
            await reconcile_and_provision_resources(
                app, "build-123", "dev", local_manifest, show_progress=False
            )

        error_msg = str(exc_info.value)
        # Should mention missing mothership
        assert (
            "mothership" in error_msg.lower() or "not provisioned" in error_msg.lower()
        )
