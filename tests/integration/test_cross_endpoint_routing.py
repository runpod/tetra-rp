"""Integration tests for cross-endpoint routing."""

from unittest.mock import AsyncMock, patch

import pytest

from tetra_rp.runtime.directory_client import DirectoryClient
from tetra_rp.runtime.http_client import CrossEndpointClient
from tetra_rp.runtime.production_wrapper import (
    ProductionWrapper,
    create_production_wrapper,
    reset_wrapper,
)
from tetra_rp.runtime.service_registry import ServiceRegistry


class TestCrossEndpointRoutingIntegration:
    """Integration tests for full cross-endpoint routing flow."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up wrapper singleton between tests."""
        yield
        reset_wrapper()

    @pytest.fixture
    def manifest(self):
        """Sample manifest with multiple endpoints."""
        return {
            "version": "1.0",
            "project_name": "integration_test",
            "function_registry": {
                "gpu_task": "gpu_config",
                "cpu_task": "cpu_config",
                "preprocess": "cpu_config",
            },
            "resources": {
                "gpu_config": {
                    "resource_type": "LiveServerless",
                    "handler_file": "handler_gpu.py",
                    "functions": [
                        {"name": "gpu_task", "module": "workers.gpu", "is_async": True}
                    ],
                },
                "cpu_config": {
                    "resource_type": "LiveServerless",
                    "handler_file": "handler_cpu.py",
                    "functions": [
                        {
                            "name": "cpu_task",
                            "module": "workers.cpu",
                            "is_async": False,
                        },
                        {
                            "name": "preprocess",
                            "module": "workers.cpu",
                            "is_async": False,
                        },
                    ],
                },
            },
        }

    @pytest.mark.asyncio
    async def test_local_function_execution(self, manifest):
        """Test that local function executes without remote call."""
        # Current endpoint is GPU
        with patch.dict(
            "os.environ",
            {
                "RUNPOD_ENDPOINT_ID": "gpu_config",
                "FLASH_MOTHERSHIP_URL": "https://mothership.example.com",
            },
        ):
            # Mock directory to have both endpoints
            directory = {
                "gpu_config": "https://gpu.example.com",
                "cpu_config": "https://cpu.example.com",
            }

            # Create temp manifest file
            import tempfile
            import json
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(manifest, f)
                manifest_path = Path(f.name)

            try:
                # Create mock registry
                registry = ServiceRegistry(manifest_path=manifest_path)

                # Mock the directory client
                mock_dir_client = AsyncMock(spec=DirectoryClient)
                mock_dir_client.get_directory.return_value = directory

                # Inject mock into registry
                registry._directory_client = mock_dir_client
                registry._directory = directory
                registry._directory_loaded_at = float("inf")  # Prevent reload

                # Create mock HTTP client (should not be called)
                http_client = AsyncMock(spec=CrossEndpointClient)

                # Create wrapper
                wrapper = ProductionWrapper(registry, http_client)

                # Create test function
                async def gpu_task(x):
                    return x * 2

                # Create mock original stub (will be called for local execution)
                original_stub = AsyncMock()
                original_stub.return_value = 42

                # Execute - should call original stub
                await wrapper.wrap_function_execution(
                    original_stub,
                    gpu_task,
                    None,
                    None,
                    True,
                    5,
                )

                # Should have called original stub
                original_stub.assert_called_once()
                # Should NOT have called HTTP client
                http_client.execute.assert_not_called()

            finally:
                manifest_path.unlink()

    @pytest.mark.asyncio
    async def test_remote_function_execution_routing(self, manifest):
        """Test that remote function is routed via HTTP."""
        # Current endpoint is GPU, calling CPU function
        with patch.dict(
            "os.environ",
            {
                "RUNPOD_ENDPOINT_ID": "gpu_config",
                "FLASH_MOTHERSHIP_URL": "https://mothership.example.com",
            },
        ):
            directory = {
                "gpu_config": "https://gpu.example.com",
                "cpu_config": "https://cpu.example.com",
            }

            import tempfile
            import json
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(manifest, f)
                manifest_path = Path(f.name)

            try:
                registry = ServiceRegistry(manifest_path=manifest_path)
                mock_dir_client = AsyncMock(spec=DirectoryClient)
                mock_dir_client.get_directory.return_value = directory
                registry._directory_client = mock_dir_client
                registry._directory = directory
                registry._directory_loaded_at = float("inf")

                http_client = AsyncMock(spec=CrossEndpointClient)
                http_client.execute.return_value = {
                    "success": True,
                    "result": "processed",
                }

                wrapper = ProductionWrapper(registry, http_client)

                # CPU function (remote from GPU endpoint)
                async def cpu_task(x):
                    return x * 3

                original_stub = AsyncMock()

                # Execute - should route via HTTP
                result = await wrapper.wrap_function_execution(
                    original_stub,
                    cpu_task,
                    None,
                    None,
                    True,
                    10,
                )

                # Should NOT have called original stub
                original_stub.assert_not_called()
                # Should have called HTTP client
                http_client.execute.assert_called_once()
                assert result == "processed"

            finally:
                manifest_path.unlink()

    @pytest.mark.asyncio
    async def test_directory_loading_on_demand(self, manifest):
        """Test that directory is loaded on-demand before routing decision."""
        with patch.dict(
            "os.environ",
            {
                "RUNPOD_ENDPOINT_ID": "gpu_config",
                "FLASH_MOTHERSHIP_URL": "https://mothership.example.com",
            },
        ):
            directory = {
                "gpu_config": "https://gpu.example.com",
                "cpu_config": "https://cpu.example.com",
            }

            import tempfile
            import json
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(manifest, f)
                manifest_path = Path(f.name)

            try:
                registry = ServiceRegistry(manifest_path=manifest_path)
                mock_dir_client = AsyncMock(spec=DirectoryClient)
                mock_dir_client.get_directory.return_value = directory
                registry._directory_client = mock_dir_client

                # Directory not loaded initially
                assert registry._directory == {}

                http_client = AsyncMock(spec=CrossEndpointClient)
                http_client.execute.return_value = {"success": True, "result": "done"}

                wrapper = ProductionWrapper(registry, http_client)

                async def cpu_task(x):
                    return x

                original_stub = AsyncMock()

                # Execute - should load directory first
                await wrapper.wrap_function_execution(
                    original_stub, cpu_task, None, None, True
                )

                # Directory should now be loaded
                assert len(registry._directory) > 0
                assert registry._directory["gpu_config"] == "https://gpu.example.com"

            finally:
                manifest_path.unlink()

    @pytest.mark.asyncio
    async def test_error_handling_in_remote_execution(self, manifest):
        """Test that errors from remote execution are properly propagated."""
        with patch.dict(
            "os.environ",
            {
                "RUNPOD_ENDPOINT_ID": "gpu_config",
                "FLASH_MOTHERSHIP_URL": "https://mothership.example.com",
            },
        ):
            directory = {
                "gpu_config": "https://gpu.example.com",
                "cpu_config": "https://cpu.example.com",
            }

            import tempfile
            import json
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(manifest, f)
                manifest_path = Path(f.name)

            try:
                registry = ServiceRegistry(manifest_path=manifest_path)
                mock_dir_client = AsyncMock(spec=DirectoryClient)
                mock_dir_client.get_directory.return_value = directory
                registry._directory_client = mock_dir_client
                registry._directory = directory
                registry._directory_loaded_at = float("inf")

                # HTTP client returns error
                http_client = AsyncMock(spec=CrossEndpointClient)
                http_client.execute.return_value = {
                    "success": False,
                    "error": "Remote function failed: ValueError",
                }

                wrapper = ProductionWrapper(registry, http_client)

                async def cpu_task():
                    pass

                original_stub = AsyncMock()

                # Execute - should raise error from remote
                with pytest.raises(Exception, match="Remote execution.*failed"):
                    await wrapper.wrap_function_execution(
                        original_stub, cpu_task, None, None, True
                    )

            finally:
                manifest_path.unlink()

    def test_factory_creates_complete_system(self):
        """Test that factory creates fully integrated system."""
        import tempfile
        import json
        from pathlib import Path

        manifest = {
            "version": "1.0",
            "project_name": "test",
            "function_registry": {"task": "resource1"},
            "resources": {
                "resource1": {
                    "functions": [{"name": "task", "module": "m", "is_async": True}]
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(manifest, f)
            manifest_path = Path(f.name)

        try:
            with patch.dict(
                "os.environ",
                {
                    "RUNPOD_ENDPOINT_ID": "resource1",
                    "FLASH_MOTHERSHIP_URL": "https://mothership.example.com",
                },
            ):
                wrapper = create_production_wrapper()

                # Should have created registry
                assert wrapper.service_registry is not None
                assert isinstance(wrapper.service_registry, ServiceRegistry)

                # Should have created HTTP client
                assert wrapper.http_client is not None
                assert isinstance(wrapper.http_client, CrossEndpointClient)

        finally:
            manifest_path.unlink()
            reset_wrapper()
