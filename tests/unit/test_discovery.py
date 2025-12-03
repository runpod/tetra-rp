"""Unit tests for ResourceDiscovery."""

import pytest
from textwrap import dedent

from tetra_rp.core.discovery import ResourceDiscovery
from tetra_rp.core.resources.serverless import ServerlessResource


class TestResourceDiscovery:
    """Test ResourceDiscovery functionality."""

    @pytest.fixture
    def temp_entry_point(self, tmp_path):
        """Create temporary entry point file for testing."""
        entry_file = tmp_path / "main.py"
        return entry_file

    @pytest.fixture
    def sample_resource_config(self):
        """Create sample resource config for testing."""
        return ServerlessResource(
            name="test-gpu",
            gpuCount=1,
            workersMax=3,
            workersMin=0,
            flashboot=False,
        )

    def test_discover_no_remote_decorators(self, temp_entry_point):
        """Test discovery when no @remote decorators exist."""
        temp_entry_point.write_text(
            dedent(
                """
                from fastapi import FastAPI

                app = FastAPI()

                @app.get("/")
                def root():
                    return {"message": "Hello"}
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        assert resources == []

    def test_discover_single_remote_decorator(self, temp_entry_point):
        """Test discovery of single @remote decorator."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                gpu_config = ServerlessResource(
                    name="test-gpu",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                @remote(resource_config=gpu_config)
                async def gpu_task():
                    return "result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        assert len(resources) == 1
        assert isinstance(resources[0], ServerlessResource)
        assert resources[0].name == "test-gpu"

    def test_discover_multiple_remote_decorators(self, temp_entry_point):
        """Test discovery of multiple @remote decorators."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                gpu_config = ServerlessResource(
                    name="gpu-endpoint",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                cpu_config = ServerlessResource(
                    name="cpu-endpoint",
                    gpuCount=0,
                    workersMax=5,
                    workersMin=1,
                    flashboot=False,
                )

                @remote(resource_config=gpu_config)
                async def gpu_task():
                    return "gpu result"

                @remote(resource_config=cpu_config)
                async def cpu_task():
                    return "cpu result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        assert len(resources) == 2
        names = {r.name for r in resources}
        assert names == {"gpu-endpoint", "cpu-endpoint"}

    def test_discover_positional_argument(self, temp_entry_point):
        """Test discovery with positional argument @remote(config)."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                my_config = ServerlessResource(
                    name="test-endpoint",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                @remote(my_config)
                async def my_task():
                    return "result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        assert len(resources) == 1
        assert resources[0].name == "test-endpoint"

    def test_discover_invalid_import(self, temp_entry_point):
        """Test discovery handles invalid imports gracefully."""
        temp_entry_point.write_text(
            dedent(
                """
                import nonexistent_module

                from tetra_rp.client import remote
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        # Should handle import error gracefully
        assert isinstance(resources, list)

    def test_discover_cache(self, temp_entry_point):
        """Test that discovery results are cached."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                config = ServerlessResource(
                    name="cached-endpoint",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                @remote(config)
                async def task():
                    return "result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))

        # First call
        resources1 = discovery.discover()
        assert len(resources1) == 1

        # Second call should use cache
        resources2 = discovery.discover()
        assert resources1 == resources2

    def test_clear_cache(self, temp_entry_point):
        """Test clearing discovery cache."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                config = ServerlessResource(
                    name="test-endpoint",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                @remote(config)
                async def task():
                    return "result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()
        assert len(resources) == 1

        # Clear cache
        discovery.clear_cache()
        assert discovery._cache == {}

    def test_discover_with_syntax_error(self, temp_entry_point):
        """Test discovery handles syntax errors gracefully."""
        temp_entry_point.write_text(
            dedent(
                """
                def invalid_syntax(
                    # Missing closing parenthesis
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        # Should handle parse error gracefully
        assert isinstance(resources, list)

    def test_discover_non_deployable_resource(self, temp_entry_point):
        """Test discovery skips non-DeployableResource objects."""
        temp_entry_point.write_text(
            dedent(
                """
                from tetra_rp.client import remote

                # Not a DeployableResource
                config = {"name": "not-a-resource"}

                @remote(resource_config=config)
                async def task():
                    return "result"
                """
            )
        )

        discovery = ResourceDiscovery(str(temp_entry_point))
        resources = discovery.discover()

        # Should skip non-DeployableResource
        assert resources == []

    def test_max_depth_limiting(self, tmp_path):
        """Test that recursive scanning respects max_depth."""
        # Create nested module structure
        entry_file = tmp_path / "main.py"
        level1_file = tmp_path / "level1.py"
        level2_file = tmp_path / "level2.py"
        level3_file = tmp_path / "level3.py"

        entry_file.write_text("import level1")
        level1_file.write_text("import level2")
        level2_file.write_text("import level3")
        level3_file.write_text("# Too deep")

        discovery = ResourceDiscovery(str(entry_file), max_depth=2)
        resources = discovery.discover()

        # Should respect max_depth and not crash
        assert isinstance(resources, list)
