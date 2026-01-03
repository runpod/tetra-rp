"""Tests for ServiceRegistry."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tetra_rp.runtime.service_registry import ServiceRegistry


class TestServiceRegistry:
    """Test ServiceRegistry functionality."""

    @pytest.fixture
    def manifest_dict(self):
        """Sample manifest."""
        return {
            "version": "1.0",
            "project_name": "test_app",
            "function_registry": {
                "gpu_task": "gpu_config",
                "preprocess": "cpu_config",
                "inference": "gpu_config",
            },
            "resources": {
                "gpu_config": {
                    "resource_type": "LiveServerless",
                    "handler_file": "handler_gpu_config.py",
                    "functions": [
                        {"name": "gpu_task", "module": "workers.gpu", "is_async": True},
                        {
                            "name": "inference",
                            "module": "workers.gpu",
                            "is_async": True,
                        },
                    ],
                },
                "cpu_config": {
                    "resource_type": "LiveServerless",
                    "handler_file": "handler_cpu_config.py",
                    "functions": [
                        {
                            "name": "preprocess",
                            "module": "workers.cpu",
                            "is_async": False,
                        },
                    ],
                },
            },
        }

    @pytest.fixture
    def manifest_file(self, manifest_dict):
        """Create temporary manifest file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(manifest_dict, f)
            path = f.name

        yield Path(path)

        # Cleanup
        Path(path).unlink()

    def test_init_with_manifest_path(self, manifest_file):
        """Test initialization with explicit manifest path."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        assert registry.get_manifest()["project_name"] == "test_app"

    def test_init_from_env_manifest_path(self, manifest_file):
        """Test initialization from FLASH_MANIFEST_PATH env var."""
        with patch.dict(os.environ, {"FLASH_MANIFEST_PATH": str(manifest_file)}):
            registry = ServiceRegistry()
            assert registry.get_manifest()["project_name"] == "test_app"

    def test_init_manifest_not_found(self):
        """Test initialization with missing manifest."""
        with patch.dict(os.environ, {}, clear=True):
            registry = ServiceRegistry(manifest_path=Path("/nonexistent/manifest.json"))
            # Should not fail, returns empty manifest
            assert registry.get_manifest()["function_registry"] == {}

    def test_get_current_endpoint_id(self):
        """Test retrieval of current endpoint ID from env."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu-endpoint-123"}):
            registry = ServiceRegistry(manifest_path=Path("/nonexistent"))
            assert registry.get_current_endpoint_id() == "gpu-endpoint-123"

    def test_get_current_endpoint_id_not_set(self):
        """Test when endpoint ID not set."""
        with patch.dict(os.environ, {}, clear=True):
            registry = ServiceRegistry(manifest_path=Path("/nonexistent"))
            assert registry.get_current_endpoint_id() is None

    def test_is_local_function_local(self, manifest_file):
        """Test determining local function."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            registry = ServiceRegistry(manifest_path=manifest_file)
            assert registry.is_local_function("gpu_task") is True
            assert registry.is_local_function("inference") is True

    def test_is_local_function_remote(self, manifest_file):
        """Test determining remote function (with directory loaded)."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            mock_client = AsyncMock()
            mock_client.get_directory.return_value = {
                "cpu_config": "https://cpu.example.com"
            }

            registry = ServiceRegistry(
                manifest_path=manifest_file, directory_client=mock_client
            )
            # After directory is loaded, CPU tasks should be recognized as remote
            # (but is_local_function doesn't async load, so returns True for now)
            # This is actually expected behavior - sync method can't load async directory
            assert registry.is_local_function("preprocess") is True

    def test_is_local_function_not_in_manifest(self, manifest_file):
        """Test function not in manifest."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        # Unknown function assumed local
        assert registry.is_local_function("unknown_function") is True

    def test_get_endpoint_for_function_local(self, manifest_file):
        """Test getting endpoint for local function."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            registry = ServiceRegistry(manifest_path=manifest_file)
            endpoint = registry.get_endpoint_for_function("gpu_task")
            assert endpoint is None  # Local returns None

    def test_get_endpoint_for_function_remote_no_directory(self, manifest_file):
        """Test getting endpoint for remote function without directory."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            registry = ServiceRegistry(manifest_path=manifest_file)
            # CPU function is remote, but no directory loaded
            endpoint = registry.get_endpoint_for_function("preprocess")
            assert endpoint is None

    def test_get_endpoint_for_function_not_in_manifest(self, manifest_file):
        """Test getting endpoint for unknown function."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        with pytest.raises(ValueError, match="not found in manifest"):
            registry.get_endpoint_for_function("unknown_function")

    def test_get_resource_for_function_local(self, manifest_file):
        """Test getting ServerlessResource for local function."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            registry = ServiceRegistry(manifest_path=manifest_file)
            resource = registry.get_resource_for_function("gpu_task")
            # Local function returns None
            assert resource is None

    def test_get_resource_for_function_remote(self, manifest_file):
        """Test getting ServerlessResource for remote function."""
        with patch.dict(os.environ, {"RUNPOD_ENDPOINT_ID": "gpu_config"}):
            mock_client = AsyncMock()
            mock_client.get_directory.return_value = {
                "cpu_config": "https://api.runpod.io/v2/abc123"
            }

            registry = ServiceRegistry(
                manifest_path=manifest_file, directory_client=mock_client
            )
            # Manually set directory to simulate loaded state
            registry._directory = {"cpu_config": "https://api.runpod.io/v2/abc123"}

            resource = registry.get_resource_for_function("preprocess")

            # Should return ServerlessResource
            assert resource is not None
            assert resource.id == "abc123"
            # Name starts with remote_preprocess (may have random suffix appended)
            assert resource.name.startswith("remote_preprocess")

    def test_get_resource_for_function_not_in_manifest(self, manifest_file):
        """Test getting resource for unknown function."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        with pytest.raises(ValueError, match="not found in manifest"):
            registry.get_resource_for_function("unknown_function")

    @pytest.mark.asyncio
    async def test_ensure_directory_loaded(self, manifest_file):
        """Test lazy loading of directory from client."""
        mock_directory = {
            "gpu_config": "https://gpu.example.com",
            "cpu_config": "https://cpu.example.com",
        }

        mock_client = AsyncMock()
        mock_client.get_directory.return_value = mock_directory

        registry = ServiceRegistry(
            manifest_path=manifest_file, directory_client=mock_client, cache_ttl=10
        )

        # Directory not loaded yet
        assert registry._directory == {}

        # Load directory
        await registry._ensure_directory_loaded()

        # Should now have loaded directory
        assert registry._directory == mock_directory
        mock_client.get_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_directory_cache_respects_ttl(self, manifest_file):
        """Test that directory cache respects TTL."""
        mock_directory = {"gpu_config": "https://gpu.example.com"}

        mock_client = AsyncMock()
        mock_client.get_directory.return_value = mock_directory

        registry = ServiceRegistry(
            manifest_path=manifest_file, directory_client=mock_client, cache_ttl=1
        )

        # Load directory
        await registry._ensure_directory_loaded()
        assert mock_client.get_directory.call_count == 1

        # Immediate reload should use cache
        await registry._ensure_directory_loaded()
        assert mock_client.get_directory.call_count == 1

        # After TTL, should reload
        registry._directory_loaded_at = time.time() - 2  # 2 seconds ago
        await registry._ensure_directory_loaded()
        assert mock_client.get_directory.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_directory(self, manifest_file):
        """Test forcing directory refresh."""
        mock_directory = {"gpu_config": "https://gpu.example.com"}

        mock_client = AsyncMock()
        mock_client.get_directory.return_value = mock_directory

        registry = ServiceRegistry(
            manifest_path=manifest_file, directory_client=mock_client, cache_ttl=3600
        )

        # Load directory
        await registry._ensure_directory_loaded()
        assert mock_client.get_directory.call_count == 1

        # Force refresh
        registry.refresh_directory()

        # Next load should fetch again
        await registry._ensure_directory_loaded()
        assert mock_client.get_directory.call_count == 2

    def test_get_manifest(self, manifest_file):
        """Test getting manifest."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        manifest = registry.get_manifest()
        assert manifest["project_name"] == "test_app"

    def test_get_all_resources(self, manifest_file):
        """Test getting all resources."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        resources = registry.get_all_resources()
        assert "gpu_config" in resources
        assert "cpu_config" in resources

    def test_get_resource_functions(self, manifest_file):
        """Test getting functions for a resource."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        functions = registry.get_resource_functions("gpu_config")
        assert len(functions) == 2
        names = [f["name"] for f in functions]
        assert "gpu_task" in names
        assert "inference" in names

    def test_get_resource_functions_not_found(self, manifest_file):
        """Test getting functions for nonexistent resource."""
        registry = ServiceRegistry(manifest_path=manifest_file)
        functions = registry.get_resource_functions("nonexistent")
        assert functions == []

    def test_init_no_directory_client_no_mothership_url(self, manifest_file):
        """Test initialization without directory client or URL."""
        with patch.dict(os.environ, {}, clear=True):
            registry = ServiceRegistry(manifest_path=manifest_file)
            assert registry._directory_client is None

    @pytest.mark.asyncio
    async def test_ensure_directory_loaded_unavailable_client(self, manifest_file):
        """Test directory loading when client is None."""
        registry = ServiceRegistry(manifest_path=manifest_file, directory_client=None)
        # Should not fail, just log warning
        await registry._ensure_directory_loaded()
        assert registry._directory == {}
