"""Unit tests for undeploy CLI command."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typer.testing import CliRunner

from tetra_rp.cli.main import app
from tetra_rp.core.resources.serverless import ServerlessResource
from tetra_rp.core.resources.resource_manager import ResourceManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton state before each test."""
    ResourceManager._resources = {}
    ResourceManager._deployment_locks = {}
    ResourceManager._resources_initialized = False
    ResourceManager._lock_initialized = False
    yield
    ResourceManager._resources = {}
    ResourceManager._deployment_locks = {}
    ResourceManager._resources_initialized = False
    ResourceManager._lock_initialized = False


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_resources():
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

    return {
        resource1.resource_id: resource1,
        resource2.resource_id: resource2,
    }


class TestUndeployList:
    """Test undeploy list command."""

    def test_list_no_endpoints(self, runner):
        """Test list command with no endpoints."""
        with patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM:
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = {}
            MockRM.return_value = mock_manager

            result = runner.invoke(app, ["undeploy", "list"])

            assert result.exit_code == 0
            assert "No endpoints found" in result.stdout

    def test_list_with_endpoints(self, runner):
        """Test list command with endpoints."""
        # Create mock resources instead of real ones to avoid Pydantic issues
        mock_resource1 = MagicMock()
        mock_resource1.name = "test-api-1"
        mock_resource1.id = "endpoint-id-1"
        mock_resource1.is_deployed.return_value = True
        mock_resource1.__class__.__name__ = "ServerlessResource"

        mock_resource2 = MagicMock()
        mock_resource2.name = "test-api-2"
        mock_resource2.id = "endpoint-id-2"
        mock_resource2.is_deployed.return_value = True
        mock_resource2.__class__.__name__ = "ServerlessResource"

        mock_resources = {
            "resource-id-1": mock_resource1,
            "resource-id-2": mock_resource2,
        }

        with patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM:
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = mock_resources
            MockRM.return_value = mock_manager

            result = runner.invoke(app, ["undeploy", "list"])

            # Print output for debugging
            if result.exit_code != 0:
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr if hasattr(result, "stderr") else "N/A")
                if result.exception:
                    print("EXCEPTION:", result.exception)
                    import traceback

                    traceback.print_exception(
                        type(result.exception),
                        result.exception,
                        result.exception.__traceback__,
                    )

            assert result.exit_code == 0
            assert "test-api-1" in result.stdout
            assert "test-api-2" in result.stdout
            assert "endpoint-id-1" in result.stdout
            assert "endpoint-id-2" in result.stdout


class TestUndeployCommand:
    """Test undeploy command."""

    def test_undeploy_no_args_shows_help(self, runner):
        """Test undeploy without arguments shows help/usage."""
        result = runner.invoke(app, ["undeploy"])

        # With no args, Typer shows help (exit_code 0) due to no_args_is_help
        assert result.exit_code == 0
        assert "Usage" in result.stdout or "undeploy" in result.stdout.lower()

    def test_undeploy_nonexistent_name(self, runner, sample_resources):
        """Test undeploy with nonexistent name."""
        with patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM:
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = sample_resources
            MockRM.return_value = mock_manager

            result = runner.invoke(app, ["undeploy", "nonexistent"])

            assert result.exit_code == 1
            assert "no endpoint found" in result.stdout.lower()

    def test_undeploy_by_name_cancelled(self, runner, sample_resources):
        """Test undeploy by name cancelled by user."""
        with (
            patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM,
            patch("tetra_rp.cli.commands.undeploy.questionary") as mock_questionary,
        ):
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = sample_resources
            MockRM.return_value = mock_manager

            # User cancels confirmation
            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = False
            mock_questionary.confirm.return_value = mock_confirm

            result = runner.invoke(app, ["undeploy", "test-api-1"])

            assert result.exit_code == 0
            assert "cancelled" in result.stdout.lower()

    @patch("tetra_rp.cli.commands.undeploy.asyncio.run")
    def test_undeploy_by_name_success(self, mock_asyncio_run, runner, sample_resources):
        """Test successful undeploy by name."""
        with (
            patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM,
            patch("tetra_rp.cli.commands.undeploy.questionary") as mock_questionary,
        ):
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = sample_resources
            MockRM.return_value = mock_manager

            # User confirms
            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_questionary.confirm.return_value = mock_confirm

            # Mock successful deletion
            mock_asyncio_run.return_value = {
                "success": True,
                "name": "test-api-1",
                "endpoint_id": "endpoint-id-1",
                "message": "Successfully deleted",
            }

            result = runner.invoke(app, ["undeploy", "test-api-1"])

            assert result.exit_code == 0
            assert "Successfully deleted" in result.stdout

    @patch("tetra_rp.cli.commands.undeploy.asyncio.run")
    def test_undeploy_all_flag(self, mock_asyncio_run, runner, sample_resources):
        """Test undeploy --all flag."""
        with (
            patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM,
            patch("tetra_rp.cli.commands.undeploy.questionary") as mock_questionary,
        ):
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = sample_resources
            MockRM.return_value = mock_manager

            # User confirms both prompts
            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_text = MagicMock()
            mock_text.ask.return_value = "DELETE ALL"

            mock_questionary.confirm.return_value = mock_confirm
            mock_questionary.text.return_value = mock_text

            # Mock successful deletions
            mock_asyncio_run.return_value = {
                "success": True,
                "name": "test-api",
                "endpoint_id": "endpoint-id",
                "message": "Successfully deleted",
            }

            result = runner.invoke(app, ["undeploy", "--all"])

            assert result.exit_code == 0
            assert "Successfully deleted" in result.stdout

    def test_undeploy_all_wrong_confirmation(self, runner, sample_resources):
        """Test undeploy --all with wrong confirmation text."""
        with (
            patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM,
            patch("tetra_rp.cli.commands.undeploy.questionary") as mock_questionary,
        ):
            mock_manager = MagicMock()
            mock_manager.list_all_resources.return_value = sample_resources
            MockRM.return_value = mock_manager

            # User confirms first prompt but wrong text on second
            mock_confirm = MagicMock()
            mock_confirm.ask.return_value = True
            mock_text = MagicMock()
            mock_text.ask.return_value = "wrong text"

            mock_questionary.confirm.return_value = mock_confirm
            mock_questionary.text.return_value = mock_text

            result = runner.invoke(app, ["undeploy", "--all"])

            assert result.exit_code == 1
            assert "Confirmation failed" in result.stdout


class TestDeleteEndpoint:
    """Test _delete_endpoint helper function."""

    @pytest.mark.asyncio
    async def test_delete_endpoint_success(self, sample_resources):
        """Test successful endpoint deletion."""
        from tetra_rp.cli.commands.undeploy import _delete_endpoint

        resource = list(sample_resources.values())[0]
        endpoint_id = resource.id
        resource_id = resource.resource_id
        name = resource.name

        with (
            patch("tetra_rp.cli.commands.undeploy.RunpodGraphQLClient") as MockClient,
            patch("tetra_rp.cli.commands.undeploy.ResourceManager") as MockRM,
        ):
            # Mock successful API deletion
            mock_client = AsyncMock()
            mock_client.delete_endpoint.return_value = {"success": True}
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            # Mock manager
            mock_manager = MagicMock()
            MockRM.return_value = mock_manager

            result = await _delete_endpoint(endpoint_id, resource_id, name)

            assert result["success"] is True
            assert result["name"] == name
            assert result["endpoint_id"] == endpoint_id
            mock_manager.remove_resource.assert_called_once_with(resource_id)

    @pytest.mark.asyncio
    async def test_delete_endpoint_api_failure(self):
        """Test endpoint deletion with API failure (malformed response)."""
        from tetra_rp.cli.commands.undeploy import _delete_endpoint

        with patch("tetra_rp.cli.commands.undeploy.RunpodGraphQLClient") as MockClient:
            # Mock failed API deletion - returns empty dict (missing deleteEndpoint key)
            mock_client = AsyncMock()
            mock_client.delete_endpoint.return_value = {"success": False}
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            result = await _delete_endpoint("endpoint-id", "resource-id", "test-name")

            assert result["success"] is False
            assert "Failed to delete" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_endpoint_exception(self):
        """Test endpoint deletion with exception."""
        from tetra_rp.cli.commands.undeploy import _delete_endpoint

        with patch("tetra_rp.cli.commands.undeploy.RunpodGraphQLClient") as MockClient:
            # Mock exception during deletion
            mock_client = AsyncMock()
            mock_client.delete_endpoint.side_effect = Exception("API Error")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            result = await _delete_endpoint("endpoint-id", "resource-id", "test-name")

            assert result["success"] is False
            assert "Error deleting" in result["message"]
            assert "API Error" in result["message"]


class TestResourceStatusHelpers:
    """Test helper functions for resource status."""

    def test_get_resource_status_active(self):
        """Test _get_resource_status for active resource."""
        from tetra_rp.cli.commands.undeploy import _get_resource_status

        mock_resource = MagicMock()
        mock_resource.is_deployed.return_value = True

        icon, text = _get_resource_status(mock_resource)

        assert icon == "🟢"
        assert text == "Active"

    def test_get_resource_status_inactive(self):
        """Test _get_resource_status for inactive resource."""
        from tetra_rp.cli.commands.undeploy import _get_resource_status

        mock_resource = MagicMock()
        mock_resource.is_deployed.return_value = False

        icon, text = _get_resource_status(mock_resource)

        assert icon == "🔴"
        assert text == "Inactive"

    def test_get_resource_status_exception(self):
        """Test _get_resource_status when exception occurs."""
        from tetra_rp.cli.commands.undeploy import _get_resource_status

        mock_resource = MagicMock()
        mock_resource.is_deployed.side_effect = Exception("API Error")

        icon, text = _get_resource_status(mock_resource)

        assert icon == "❓"
        assert text == "Unknown"

    def test_get_resource_type(self, sample_resources):
        """Test _get_resource_type returns formatted type."""
        from tetra_rp.cli.commands.undeploy import _get_resource_type

        resource = list(sample_resources.values())[0]
        resource_type = _get_resource_type(resource)

        assert "Serverless" in resource_type
