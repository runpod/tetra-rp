"""Integration tests for StateManagerClient using Runpod GraphQL API.

Requires:
- RUNPOD_API_KEY
"""

import os
from pathlib import Path
import uuid

import pytest

from tetra_rp.core.api.runpod import RunpodGraphQLClient
from tetra_rp.runtime.state_manager_client import StateManagerClient


TEST_APP_NAME = "state-manager-test-app"
TEST_ENV_NAME = "state-manager-test-env"
TEST_TARBALL = (
    Path(__file__).resolve().parents[2] / "test-app" / ".flash" / "archive.tar.gz"
)


async def _fetch_manifest(build_id: str):
    async with RunpodGraphQLClient() as client:
        build = await client.get_flash_build(build_id)
    return build.get("manifest") or {}


@pytest.fixture(scope="session")
async def state_manager_context():
    if not os.getenv("RUNPOD_API_KEY"):
        pytest.skip("RUNPOD_API_KEY not set")

    if not TEST_TARBALL.exists():
        pytest.skip(f"Missing test tarball at {TEST_TARBALL}")

    async with RunpodGraphQLClient() as client:
        app = await client.create_flash_app({"name": TEST_APP_NAME})
        app_id = app["id"]
        environment = await client.create_flash_environment(
            {"flashAppId": app_id, "name": TEST_ENV_NAME}
        )
        env_id = environment["id"]

        upload = await client.prepare_artifact_upload(
            {"flashAppId": app_id, "tarballSize": TEST_TARBALL.stat().st_size}
        )
        object_key = upload["objectKey"]

    import requests

    with TEST_TARBALL.open("rb") as handle:
        response = requests.put(
            upload["uploadUrl"],
            data=handle,
            headers={"Content-Type": "application/gzip"},
        )
        response.raise_for_status()

    async with RunpodGraphQLClient() as client:
        build = await client.finalize_artifact_upload(
            {"flashAppId": app_id, "objectKey": object_key}
        )
        build_id = build["id"]
        await client.deploy_build_to_environment(
            {"flashEnvironmentId": env_id, "flashBuildId": build_id}
        )
        await client.update_build_manifest(build_id, {"resources": {}})

    try:
        yield {
            "env_id": env_id,
            "build_id": build_id,
            "app_id": app_id,
        }
    finally:
        async with RunpodGraphQLClient() as client:
            await client.delete_flash_environment(env_id)
            await client.delete_flash_app(app_id)


class TestStateManagerClientIntegration:
    """Integration tests for StateManagerClient behavior."""

    @pytest.mark.asyncio
    async def test_get_persisted_manifest(self, state_manager_context):
        client = StateManagerClient()

        manifest = await client.get_persisted_manifest(state_manager_context["env_id"])

        assert manifest is not None
        assert isinstance(manifest, dict)
        print(manifest)

    @pytest.mark.asyncio
    async def test_update_resource_state_persists_entry(self, state_manager_context):
        client = StateManagerClient()
        resource_name = f"state-manager-test-{uuid.uuid4().hex[:8]}"
        resource_data = {
            "status": "deployed",
            "config_hash": "test-hash",
            "endpoint_url": "https://example.com",
        }

        await client.update_resource_state(
            state_manager_context["env_id"], resource_name, resource_data
        )

        second_resource_name = f"state-manager-test-{uuid.uuid4().hex[:8]}"
        second_resource_data = {
            "status": "deployed",
            "config_hash": "second-hash",
            "endpoint_url": "https://example.org",
        }

        await client.update_resource_state(
            state_manager_context["env_id"],
            second_resource_name,
            second_resource_data,
        )

        manifest = await _fetch_manifest(state_manager_context["build_id"])
        resources = manifest.get("resources") or {}
        print("after second update", manifest)

        assert resource_name in resources
        for key, value in resource_data.items():
            # assert resources[resource_name][key] == value
            assert resources[resource_name] == value

        assert second_resource_name in resources
        for key, value in second_resource_data.items():
            assert resources[second_resource_name][key] == value

    @pytest.mark.asyncio
    async def test_remove_resource_state_removes_entry(self, state_manager_context):
        client = StateManagerClient()
        resource_name = f"state-manager-test-{uuid.uuid4().hex[:8]}"
        resource_data = {
            "status": "deployed",
            "config_hash": "test-hash",
            "endpoint_url": "https://example.com",
        }

        await client.update_resource_state(
            state_manager_context["env_id"], resource_name, resource_data
        )
        await client.remove_resource_state(
            state_manager_context["env_id"], resource_name
        )

        manifest = await _fetch_manifest(state_manager_context["build_id"])
        resources = manifest.get("resources") or {}

        assert resource_name not in resources
