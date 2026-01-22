"""Unit tests for FlashApp hydration logic."""

import json
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tetra_rp.core.resources.app import FlashApp, _extract_manifest_from_tarball


@pytest.fixture
def mock_graphql_client():
    with patch("tetra_rp.core.resources.app.RunpodGraphQLClient") as mock_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_hydrate_short_circuits_when_already_hydrated(mock_graphql_client):
    app = FlashApp("demo", eager_hydrate=False)
    app._hydrated = True

    await app._hydrate()

    mock_graphql_client.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_hydrate_sets_id_when_app_exists(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.return_value = {"id": "app-123"}
    app = FlashApp("demo", eager_hydrate=False)

    await app._hydrate()

    assert app.id == "app-123"
    mock_graphql_client.get_flash_app_by_name.assert_awaited_once_with("demo")


@pytest.mark.asyncio
async def test_hydrate_raises_for_conflicting_ids(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.return_value = {"id": "app-123"}
    app = FlashApp("demo", id="other", eager_hydrate=False)

    with pytest.raises(ValueError):
        await app._hydrate()

    mock_graphql_client.create_flash_app.assert_not_awaited()


@pytest.mark.asyncio
async def test_hydrate_creates_app_when_missing(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.side_effect = Exception("app not found")
    mock_graphql_client.create_flash_app.return_value = {"id": "app-999"}
    app = FlashApp("demo", eager_hydrate=False)

    await app._hydrate()

    mock_graphql_client.create_flash_app.assert_awaited_once_with({"name": "demo"})
    assert app.id == "app-999"
    assert app._hydrated is True


@pytest.mark.asyncio
async def test_hydrate_propagates_unexpected_errors(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.side_effect = RuntimeError("boom")
    app = FlashApp("demo", eager_hydrate=False)

    with pytest.raises(RuntimeError):
        await app._hydrate()

    mock_graphql_client.create_flash_app.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_build_manifest_returns_manifest(mock_graphql_client):
    build_manifest = {
        "resources": {"cpu": {"type": "cpu"}},
        "resources_endpoints": {},
    }
    mock_graphql_client.get_flash_build.return_value = {
        "id": "build-123",
        "manifest": build_manifest,
    }
    app = FlashApp("demo", id="app-123", eager_hydrate=False)
    app._hydrated = True

    result = await app.get_build_manifest("build-123")

    assert result == build_manifest
    mock_graphql_client.get_flash_build.assert_awaited_once_with("build-123")


@pytest.mark.asyncio
async def test_get_build_manifest_returns_empty_dict_when_missing(mock_graphql_client):
    mock_graphql_client.get_flash_build.return_value = {"id": "build-123"}
    app = FlashApp("demo", id="app-123", eager_hydrate=False)
    app._hydrated = True

    result = await app.get_build_manifest("build-123")

    assert result == {}


@pytest.mark.asyncio
async def test_update_build_manifest_calls_graphql_client(mock_graphql_client):
    manifest = {
        "resources": {"cpu": {"type": "cpu"}},
        "resources_endpoints": {"cpu": "https://example.com"},
    }
    app = FlashApp("demo", id="app-123", eager_hydrate=False)
    app._hydrated = True

    await app.update_build_manifest("build-123", manifest)

    mock_graphql_client.update_build_manifest.assert_awaited_once_with(
        "build-123", manifest
    )


def test_extract_manifest_from_tarball_success(tmp_path):
    """Test successful extraction of manifest from tarball."""
    # Create a test tarball with manifest
    tar_file = tmp_path / "test.tar.gz"
    manifest_content = {
        "resources": {"cpu": {"type": "cpu"}},
        "resources_endpoints": {},
    }

    with tarfile.open(tar_file, "w:gz") as tar:
        # Add a test file
        manifest_json = json.dumps(manifest_content).encode("utf-8")
        import io

        manifest_info = tarfile.TarInfo(name="build/flash_manifest.json")
        manifest_info.size = len(manifest_json)
        tar.addfile(manifest_info, io.BytesIO(manifest_json))

    # Extract and verify
    result = _extract_manifest_from_tarball(tar_file)
    assert result == manifest_content


def test_extract_manifest_from_tarball_not_found(tmp_path):
    """Test extraction fails when manifest not in tarball."""
    # Create a test tarball without manifest
    tar_file = tmp_path / "test.tar.gz"

    with tarfile.open(tar_file, "w:gz") as tar:
        # Add a random file but no manifest
        content = b"test content"
        import io

        info = tarfile.TarInfo(name="some_file.txt")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))

    # Should raise ValueError
    with pytest.raises(ValueError, match="No flash_manifest.json found"):
        _extract_manifest_from_tarball(tar_file)


def test_extract_manifest_from_tarball_invalid_json(tmp_path):
    """Test extraction fails with invalid JSON."""
    # Create a test tarball with invalid JSON manifest
    tar_file = tmp_path / "test.tar.gz"
    invalid_json = b"not valid json {"

    with tarfile.open(tar_file, "w:gz") as tar:
        import io

        info = tarfile.TarInfo(name="flash_manifest.json")
        info.size = len(invalid_json)
        tar.addfile(info, io.BytesIO(invalid_json))

    # Should raise ValueError
    with pytest.raises(ValueError, match="Invalid JSON"):
        _extract_manifest_from_tarball(tar_file)


def test_extract_manifest_from_tarball_file_not_found():
    """Test extraction fails when tarball doesn't exist."""
    tar_path = Path("/nonexistent/path/test.tar.gz")

    with pytest.raises(FileNotFoundError, match="Tarball not found"):
        _extract_manifest_from_tarball(tar_path)


def test_extract_manifest_from_tarball_corrupted_tar(tmp_path):
    """Test extraction fails with corrupted tarfile."""
    # Create a file that looks like tar.gz but is actually invalid
    tar_file = tmp_path / "corrupted.tar.gz"
    tar_file.write_bytes(b"\x1f\x8b\x08\x00" + b"corrupt data" * 100)

    with pytest.raises(ValueError, match="Error reading tarball"):
        _extract_manifest_from_tarball(tar_file)


def test_extract_manifest_from_tarball_nested_path(tmp_path):
    """Test extraction finds manifest in nested directory."""
    # Create a test tarball with manifest in nested path
    tar_file = tmp_path / "test.tar.gz"
    manifest_content = {"version": "1.0", "services": []}

    with tarfile.open(tar_file, "w:gz") as tar:
        manifest_json = json.dumps(manifest_content).encode("utf-8")
        import io

        # Put manifest in a deeply nested path
        manifest_info = tarfile.TarInfo(name="app/build/nested/flash_manifest.json")
        manifest_info.size = len(manifest_json)
        tar.addfile(manifest_info, io.BytesIO(manifest_json))

    # Should find it despite nested path
    result = _extract_manifest_from_tarball(tar_file)
    assert result == manifest_content


@pytest.mark.asyncio
async def test_finalize_upload_build_passes_manifest(mock_graphql_client):
    """Test _finalize_upload_build passes manifest to GraphQL client."""
    manifest_data = {"resources": {"cpu": {"type": "cpu"}}}
    expected_response = {"id": "build-123", "manifest": manifest_data}

    mock_graphql_client.finalize_artifact_upload.return_value = expected_response

    app = FlashApp("test-app", id="app-123", eager_hydrate=False)
    app._hydrated = True

    result = await app._finalize_upload_build("object-key-123", manifest_data)

    # Verify the manifest was passed to the API
    mock_graphql_client.finalize_artifact_upload.assert_awaited_once_with(
        {
            "flashAppId": "app-123",
            "objectKey": "object-key-123",
            "manifest": manifest_data,
        }
    )
    assert result == expected_response


@pytest.mark.asyncio
async def test_upload_build_extracts_and_passes_manifest(mock_graphql_client, tmp_path):
    """Test upload_build extracts manifest from tarball and passes it."""
    # Create a test tarball with manifest
    tar_file = tmp_path / "build.tar.gz"
    manifest_content = {"resources": {"cpu": {"type": "cpu"}}}

    with tarfile.open(tar_file, "w:gz") as tar:
        manifest_json = json.dumps(manifest_content).encode("utf-8")
        import io

        manifest_info = tarfile.TarInfo(name="flash_manifest.json")
        manifest_info.size = len(manifest_json)
        tar.addfile(manifest_info, io.BytesIO(manifest_json))

    # Mock the API calls
    mock_graphql_client.prepare_artifact_upload.return_value = {
        "uploadUrl": "https://example.com/upload",
        "objectKey": "object-key-123",
    }
    mock_graphql_client.finalize_artifact_upload.return_value = {
        "id": "build-123",
        "manifest": manifest_content,
    }

    app = FlashApp("test-app", id="app-123", eager_hydrate=False)
    app._hydrated = True

    with patch("requests.put") as mock_put:
        mock_put.return_value.status_code = 200

        result = await app.upload_build(tar_file)

    # Verify finalize was called with the extracted manifest
    mock_graphql_client.finalize_artifact_upload.assert_awaited_once()
    call_args = mock_graphql_client.finalize_artifact_upload.call_args
    assert call_args[0][0]["manifest"] == manifest_content
    assert result["id"] == "build-123"
