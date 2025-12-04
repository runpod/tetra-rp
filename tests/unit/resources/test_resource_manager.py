"""Unit tests for ResourceManager."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from tetra_rp.core.resources.resource_manager import ResourceManager
from tetra_rp.core.utils.singleton import SingletonMixin
from tetra_rp.core.resources.serverless import ServerlessResource
from tetra_rp.core.exceptions import RunpodAPIKeyError


class TestResourceManager:
    """Test ResourceManager functionality."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test."""
        ResourceManager._resources = {}
        ResourceManager._deployment_locks = {}
        ResourceManager._resources_initialized = False
        ResourceManager._lock_initialized = False
        SingletonMixin._instances.pop(ResourceManager, None)
        yield
        # Cleanup after test
        ResourceManager._resources = {}
        ResourceManager._deployment_locks = {}
        ResourceManager._resources_initialized = False
        ResourceManager._lock_initialized = False
        SingletonMixin._instances.pop(ResourceManager, None)

    @pytest.fixture
    def mock_resource_file(self, tmp_path):
        """Mock the resource state file path."""
        resource_file = tmp_path / ".tetra_resources.pkl"
        with patch(
            "tetra_rp.core.resources.resource_manager.RESOURCE_STATE_FILE",
            resource_file,
        ):
            yield resource_file

    @pytest.fixture
    def sample_resources(self):
        """Create sample resources for testing."""
        resource1 = ServerlessResource(
            name="test-api-1",
            gpuCount=1,
            workersMax=3,
            workersMin=0,
            flashboot=False,  # Disable to keep original name
        )
        resource1.id = "endpoint-id-1"

        resource2 = ServerlessResource(
            name="test-api-2",
            gpuCount=1,
            workersMax=3,
            workersMin=0,
            flashboot=False,  # Disable to keep original name
        )
        resource2.id = "endpoint-id-2"

        resource3 = ServerlessResource(
            name="test-api-1",  # Same name as resource1
            gpuCount=2,  # Different config
            workersMax=5,
            workersMin=1,
            flashboot=False,  # Disable to keep original name
        )
        resource3.id = "endpoint-id-3"

        return {
            resource1.resource_id: resource1,
            resource2.resource_id: resource2,
            resource3.resource_id: resource3,
        }

    def test_list_all_resources_empty(self, mock_resource_file):
        """Test list_all_resources returns empty dict when no resources."""
        manager = ResourceManager()
        resources = manager.list_all_resources()

        assert resources == {}
        assert isinstance(resources, dict)

    def test_list_all_resources_with_data(self, mock_resource_file, sample_resources):
        """Test list_all_resources returns all tracked resources."""
        manager = ResourceManager()

        # Add resources
        for uid, resource in sample_resources.items():
            manager._resources[uid] = resource

        resources = manager.list_all_resources()

        assert len(resources) == 3
        assert set(resources.keys()) == set(sample_resources.keys())
        # Ensure it's a copy, not the original
        assert resources is not manager._resources

    def test_list_all_resources_returns_copy(
        self, mock_resource_file, sample_resources
    ):
        """Test that list_all_resources returns a copy, not reference."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        resources = manager.list_all_resources()
        resources.clear()

        # Original should still have data
        assert len(manager._resources) == 3

    def test_find_resources_by_name_no_matches(
        self, mock_resource_file, sample_resources
    ):
        """Test find_resources_by_name returns empty list when no matches."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        matches = manager.find_resources_by_name("nonexistent-name")

        assert matches == []
        assert isinstance(matches, list)

    def test_find_resources_by_name_single_match(
        self, mock_resource_file, sample_resources
    ):
        """Test find_resources_by_name returns single match."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        matches = manager.find_resources_by_name("test-api-2")

        assert len(matches) == 1
        uid, resource = matches[0]
        assert resource.name == "test-api-2"
        assert resource.id == "endpoint-id-2"

    def test_find_resources_by_name_multiple_matches(
        self, mock_resource_file, sample_resources
    ):
        """Test find_resources_by_name returns multiple matches with same name."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        matches = manager.find_resources_by_name("test-api-1")

        assert len(matches) == 2
        names = [resource.name for _, resource in matches]
        assert all(name == "test-api-1" for name in names)

        # Check that both resources are different (different configs)
        ids = [resource.id for _, resource in matches]
        assert "endpoint-id-1" in ids
        assert "endpoint-id-3" in ids

    def test_find_resources_by_name_exact_match_only(
        self, mock_resource_file, sample_resources
    ):
        """Test find_resources_by_name does exact match, not partial."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        # Should not match "test-api-1" or "test-api-2"
        matches = manager.find_resources_by_name("test-api")

        assert matches == []

    def test_find_resources_by_name_without_name_attribute(self, mock_resource_file):
        """Test find_resources_by_name handles resources without name attribute."""
        manager = ResourceManager()

        # Create a mock resource without name attribute
        mock_resource = MagicMock(spec=[])  # No attributes
        manager._resources = {"uid-1": mock_resource}

        matches = manager.find_resources_by_name("any-name")

        assert matches == []

    def test_add_and_find_resource(self, mock_resource_file):
        """Test adding a resource and finding it by name."""
        manager = ResourceManager()

        resource = ServerlessResource(
            name="my-endpoint",
            gpuCount=1,
            workersMax=3,
            workersMin=0,
            flashboot=False,  # Disable to keep original name
        )
        resource.id = "test-endpoint-id"

        with patch.object(manager, "_save_resources"):
            manager._add_resource(resource.resource_id, resource)

        # Find by name
        matches = manager.find_resources_by_name("my-endpoint")
        assert len(matches) == 1
        assert matches[0][1].name == "my-endpoint"
        assert matches[0][1].id == "test-endpoint-id"

    def test_remove_resource_updates_find_results(
        self, mock_resource_file, sample_resources
    ):
        """Test that removing a resource updates find_resources_by_name results."""
        manager = ResourceManager()
        manager._resources = sample_resources.copy()

        # Initially 2 matches for "test-api-1"
        matches = manager.find_resources_by_name("test-api-1")
        assert len(matches) == 2

        # Remove one
        uid_to_remove = matches[0][0]
        with patch.object(manager, "_save_resources"):
            manager._remove_resource(uid_to_remove)

        # Now should be 1 match
        matches_after = manager.find_resources_by_name("test-api-1")
        assert len(matches_after) == 1

    def test_list_all_resources_integration_with_add_remove(self, mock_resource_file):
        """Test list_all_resources works correctly with add and remove operations."""
        manager = ResourceManager()
        # Force clean state for this test
        manager._resources = {}

        # Initially empty
        assert len(manager.list_all_resources()) == 0

        # Add resource
        resource = ServerlessResource(
            name="test",
            gpuCount=1,
            workersMax=3,
            workersMin=0,
            flashboot=False,  # Disable to keep original name
        )

        with patch.object(manager, "_save_resources"):
            manager._add_resource(resource.resource_id, resource)

        # Should have 1 resource
        assert len(manager.list_all_resources()) == 1

        # Remove resource
        with patch.object(manager, "_save_resources"):
            manager._remove_resource(resource.resource_id)

        # Should be empty again
        assert len(manager.list_all_resources()) == 0

    @pytest.mark.asyncio
    async def test_get_or_deploy_resource_calls_do_deploy_once(
        self, mock_resource_file
    ):
        """Ensure get_or_deploy_resource triggers _do_deploy exactly once."""
        manager = ResourceManager()
        resource = ServerlessResource(name="rm-test", flashboot=False)
        resource.id = "endpoint-rm-test"

        with patch.object(ServerlessResource, "is_deployed", return_value=False):
            with patch.object(
                ServerlessResource, "_do_deploy", new=AsyncMock(return_value=resource)
            ) as mock_do_deploy:
                with patch.object(manager, "_add_resource") as mock_add:
                    result = await manager.get_or_deploy_resource(resource)

        mock_do_deploy.assert_awaited_once()
        mock_add.assert_called_once_with(resource.resource_id, resource)
        assert result is resource

    @pytest.mark.asyncio
    async def test_deploy_with_error_context_adds_resource_name(
        self, mock_resource_file
    ):
        """RunpodAPIKeyError should mention the resource name for context."""
        manager = ResourceManager()
        resource = ServerlessResource(name="error-test", flashboot=False)

        with patch.object(
            ServerlessResource,
            "_do_deploy",
            new=AsyncMock(side_effect=RunpodAPIKeyError("missing key")),
        ):
            with pytest.raises(RunpodAPIKeyError) as excinfo:
                await manager._deploy_with_error_context(resource)

        assert "error-test" in str(excinfo.value)
