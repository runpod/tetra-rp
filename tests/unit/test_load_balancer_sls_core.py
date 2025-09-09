"""
Unit tests for LoadBalancerSls core functionality.

Tests the core LoadBalancerSls client functionality including:
- HTTP client with retry logic and health checks
- Dual-capability execution (HTTP endpoints + remote execution)
- Session management and authentication
- Error handling and connection management
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from tetra_rp.core.resources.load_balancer_sls.client import (
    LoadBalancerSls,
    DeploymentClassWrapper,
    DeploymentInstanceWrapper,
)
from tetra_rp.core.resources.load_balancer_sls.exceptions import (
    LoadBalancerSlsConnectionError,
    LoadBalancerSlsAuthenticationError,
    LoadBalancerSlsExecutionError,
    LoadBalancerSlsConfigurationError,
)
from tetra_rp.protos.remote_execution import FunctionRequest


class TestLoadBalancerSlsInitialization:
    """Test LoadBalancerSls client initialization."""

    def test_loadbalancersls_init_with_endpoint_url(self):
        """Test LoadBalancerSls initialization with endpoint URL."""
        endpoint_url = "https://test-endpoint.api.runpod.ai"
        api_key = "test-api-key"

        client = LoadBalancerSls(
            endpoint_url=endpoint_url,
            api_key=api_key,
            timeout=120.0,
            max_retries=5,
            retry_delay=2.0,
        )

        assert client.endpoint_url == endpoint_url
        assert client.api_key == api_key
        assert client.timeout == 120.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        assert client._session is None
        assert not client._health_checked

    def test_loadbalancersls_init_with_env_api_key(self):
        """Test LoadBalancerSls initialization with environment API key."""
        endpoint_url = "https://test-endpoint.api.runpod.ai"

        with patch.dict("os.environ", {"RUNPOD_API_KEY": "env-api-key"}):
            client = LoadBalancerSls(endpoint_url=endpoint_url)
            assert client.api_key == "env-api-key"

    def test_loadbalancersls_init_no_endpoint_url_raises_error(self):
        """Test LoadBalancerSls initialization without endpoint URL raises error."""
        with pytest.raises(
            LoadBalancerSlsConfigurationError, match="endpoint_url is required"
        ):
            LoadBalancerSls()

    def test_loadbalancersls_init_strips_trailing_slash(self):
        """Test LoadBalancerSls initialization strips trailing slash from endpoint URL."""
        client = LoadBalancerSls(endpoint_url="https://test-endpoint.api.runpod.ai/")
        assert client.endpoint_url == "https://test-endpoint.api.runpod.ai"

    def test_loadbalancersls_init_defaults(self):
        """Test LoadBalancerSls initialization with default values."""
        client = LoadBalancerSls(endpoint_url="https://test.api.runpod.ai")

        assert client.timeout == 300.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client._health_check_retries == 3


class TestLoadBalancerSlsSessionManagement:
    """Test LoadBalancerSls HTTP session management."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai", api_key="test-api-key"
        )

    @pytest.mark.asyncio
    async def test_get_session_creates_new_session(self, client):
        """Test that _get_session creates a new aiohttp session."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            session = await client._get_session()

            assert session == mock_session
            mock_session_class.assert_called_once()

            # Check headers are set correctly
            call_args = mock_session_class.call_args
            headers = call_args.kwargs["headers"]
            assert headers["Content-Type"] == "application/json"
            assert headers["Authorization"] == "Bearer test-api-key"

    @pytest.mark.asyncio
    async def test_get_session_without_api_key(self):
        """Test _get_session without API key doesn't set Authorization header."""
        client = LoadBalancerSls(endpoint_url="https://test-endpoint.api.runpod.ai")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await client._get_session()

            call_args = mock_session_class.call_args
            headers = call_args.kwargs["headers"]
            assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing_session(self, client):
        """Test that _get_session reuses existing session."""
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        session = await client._get_session()

        assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_session_recreates_closed_session(self, client):
        """Test that _get_session recreates closed session."""
        old_session = AsyncMock()
        old_session.closed = True
        client._session = old_session

        with patch("aiohttp.ClientSession") as mock_session_class:
            new_session = AsyncMock()
            new_session.closed = False
            mock_session_class.return_value = new_session

            session = await client._get_session()

            assert session == new_session
            assert client._session == new_session

    @pytest.mark.asyncio
    async def test_close_session(self, client):
        """Test closing HTTP session."""
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()


class TestLoadBalancerSlsRequestHandling:
    """Test LoadBalancerSls HTTP request handling and retry logic."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai",
            api_key="test-api-key",
            max_retries=2,
            retry_delay=0.1,
        )

    @pytest.mark.asyncio
    async def test_make_request_with_retry_success_get(self, client):
        """Test successful GET request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"success": True, "data": "test"}
        mock_response.raise_for_status.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client._make_request_with_retry(
                "GET", "https://test-endpoint.api.runpod.ai/health", "test_operation"
            )

            assert result == {"success": True, "data": "test"}
            mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_with_retry_success_post(self, client):
        """Test successful POST request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status.return_value = None

        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        json_data = {"input": "test"}

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client._make_request_with_retry(
                "POST",
                "https://test-endpoint.api.runpod.ai/execute",
                "test_operation",
                json_data,
            )

            assert result == {"result": "success"}
            mock_session.post.assert_called_once_with(
                "https://test-endpoint.api.runpod.ai/execute", json=json_data
            )

    @pytest.mark.asyncio
    async def test_handle_response_401_authentication_error(self, client):
        """Test handling 401 authentication error."""
        mock_response = AsyncMock()
        mock_response.status = 401

        with pytest.raises(LoadBalancerSlsAuthenticationError):
            await client._handle_response(mock_response, "test_operation")

    @pytest.mark.asyncio
    async def test_handle_response_404_not_found(self, client):
        """Test handling 404 not found error."""
        mock_response = AsyncMock()
        mock_response.status = 404

        with pytest.raises(LoadBalancerSlsConnectionError, match="Endpoint not found"):
            await client._handle_response(mock_response, "test_operation")

    @pytest.mark.asyncio
    async def test_handle_response_server_error(self, client):
        """Test handling server errors (5xx)."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"

        with pytest.raises(LoadBalancerSlsConnectionError, match="HTTP 500"):
            await client._handle_response(mock_response, "test_operation")

    @pytest.mark.asyncio
    async def test_make_request_retry_on_failure(self, client):
        """Test retry logic on request failure."""
        # Mock session that fails twice then succeeds
        mock_session = AsyncMock()

        # First two calls raise exception
        mock_session.post.side_effect = [
            aiohttp.ClientError("Connection failed"),
            aiohttp.ClientError("Connection failed"),
            # Third call succeeds
            MagicMock(),
        ]

        # Mock successful response for third attempt
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch("asyncio.sleep"):  # Skip actual sleep delays in tests
                result = await client._make_request_with_retry(
                    "POST",
                    "https://test-endpoint.api.runpod.ai/test",
                    "test_op",
                    {"data": "test"},
                )

                assert result == {"success": True}
                assert mock_session.post.call_count == 3

    @pytest.mark.asyncio
    async def test_make_request_max_retries_exceeded(self, client):
        """Test that max retries exceeded raises appropriate error."""
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Persistent failure")

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch("asyncio.sleep"):
                with pytest.raises(
                    LoadBalancerSlsConnectionError, match="Failed after 3 attempts"
                ):
                    await client._make_request_with_retry(
                        "POST",
                        "https://test-endpoint.api.runpod.ai/test",
                        "test_op",
                        {"data": "test"},
                    )


class TestLoadBalancerSlsHealthChecks:
    """Test LoadBalancerSls health check functionality."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai", api_key="test-api-key"
        )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        expected_health = {"status": "healthy", "workers": 2}

        with patch.object(
            client, "_make_request_with_retry", return_value=expected_health
        ):
            result = await client.health_check()
            assert result == expected_health

    @pytest.mark.asyncio
    async def test_perform_health_check(self, client):
        """Test _perform_health_check calls correct endpoint."""
        expected_health = {"status": "healthy"}

        with patch.object(
            client, "_make_request_with_retry", return_value=expected_health
        ) as mock_request:
            result = await client._perform_health_check()

            assert result == expected_health
            mock_request.assert_called_once_with(
                "GET", f"{client.endpoint_url}/health", "health_check"
            )

    @pytest.mark.asyncio
    async def test_ensure_healthy_first_time_success(self, client):
        """Test _ensure_healthy succeeds on first attempt."""
        with patch.object(
            client, "_perform_health_check", return_value={"status": "ok"}
        ):
            await client._ensure_healthy()

            assert client._health_checked is True

    @pytest.mark.asyncio
    async def test_ensure_healthy_already_checked(self, client):
        """Test _ensure_healthy skips check if already performed."""
        client._health_checked = True

        with patch.object(client, "_perform_health_check") as mock_health:
            await client._ensure_healthy()

            mock_health.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_healthy_retry_on_failure(self, client):
        """Test _ensure_healthy retries on failure."""
        with patch.object(client, "_perform_health_check") as mock_health:
            # First two calls fail, third succeeds
            mock_health.side_effect = [
                Exception("Health check failed"),
                Exception("Health check failed"),
                {"status": "healthy"},
            ]

            with patch("asyncio.sleep"):  # Skip actual sleep
                await client._ensure_healthy()

                assert mock_health.call_count == 3
                assert client._health_checked is True

    @pytest.mark.asyncio
    async def test_ensure_healthy_max_retries_exceeded(self, client):
        """Test _ensure_healthy fails after max retries."""
        with patch.object(
            client, "_perform_health_check", side_effect=Exception("Persistent failure")
        ):
            with patch("asyncio.sleep"):
                with pytest.raises(
                    LoadBalancerSlsConnectionError,
                    match="Health check failed after 3 attempts",
                ):
                    await client._ensure_healthy()

                assert not client._health_checked


class TestLoadBalancerSlsRemoteExecution:
    """Test LoadBalancerSls remote method execution."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai", api_key="test-api-key"
        )

    @pytest.fixture
    def sample_request(self):
        return FunctionRequest(
            execution_type="class",
            class_name="TestClass",
            class_code="class TestClass: pass",
            method_name="test_method",
            args=["arg1"],
            kwargs={"key": "value"},
            constructor_args=[],
            constructor_kwargs={},
            dependencies=["numpy"],
            system_dependencies=[],
            instance_id="test_instance",
            create_new_instance=True,
        )

    @pytest.mark.asyncio
    async def test_call_remote_method_success(self, client, sample_request):
        """Test successful remote method execution."""
        mock_result = {"test": "result"}
        api_response = {"success": True, "result": mock_result}

        with patch.object(client, "_ensure_healthy"):
            with patch.object(
                client, "_make_request_with_retry", return_value=api_response
            ):
                with patch(
                    "tetra_rp.core.resources.load_balancer_sls.serialization.SerializationUtils.deserialize_result",
                    return_value=mock_result,
                ):
                    result = await client.call_remote_method(sample_request)

                    assert result == mock_result

    @pytest.mark.asyncio
    async def test_call_remote_method_execution_error(self, client, sample_request):
        """Test remote method execution error handling."""
        api_response = {"success": False, "error": "Method execution failed"}

        with patch.object(client, "_ensure_healthy"):
            with patch.object(
                client, "_make_request_with_retry", return_value=api_response
            ):
                with pytest.raises(
                    LoadBalancerSlsExecutionError,
                    match="Execution failed for test_method",
                ):
                    await client.call_remote_method(sample_request)

    @pytest.mark.asyncio
    async def test_call_http_endpoint_success(self, client):
        """Test successful HTTP endpoint call."""
        method_name = "predict"
        data = {"input": "test_data"}
        expected_result = {"prediction": "result"}

        with patch.object(client, "_ensure_healthy"):
            with patch.object(
                client, "_make_request_with_retry", return_value=expected_result
            ):
                result = await client.call_http_endpoint(method_name, data)

                assert result == expected_result

    @pytest.mark.asyncio
    async def test_remote_method_calls_ensure_healthy(self, client, sample_request):
        """Test that remote method calls ensure endpoint is healthy first."""
        api_response = {"success": True, "result": None}

        with patch.object(client, "_ensure_healthy") as mock_health:
            with patch.object(
                client, "_make_request_with_retry", return_value=api_response
            ):
                await client.call_remote_method(sample_request)

                mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_endpoint_calls_ensure_healthy(self, client):
        """Test that HTTP endpoint calls ensure endpoint is healthy first."""
        with patch.object(client, "_ensure_healthy") as mock_health:
            with patch.object(client, "_make_request_with_retry", return_value={}):
                await client.call_http_endpoint("test_method", {})

                mock_health.assert_called_once()


class TestLoadBalancerSlsRemoteClassDecorator:
    """Test LoadBalancerSls remote_class decorator functionality."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai", api_key="test-api-key"
        )

    def test_remote_class_decorator_returns_wrapper(self, client):
        """Test remote_class decorator returns DeploymentClassWrapper."""
        dependencies = ["numpy"]
        system_dependencies = ["apt-package"]

        @client.remote_class(
            dependencies=dependencies, system_dependencies=system_dependencies
        )
        class TestClass:
            def test_method(self):
                return "test"

        assert isinstance(TestClass, DeploymentClassWrapper)
        assert TestClass._dependencies == dependencies
        assert TestClass._system_dependencies == system_dependencies

    def test_remote_class_decorator_defaults(self, client):
        """Test remote_class decorator with default parameters."""

        @client.remote_class()
        class TestClass:
            def test_method(self):
                return "test"

        assert isinstance(TestClass, DeploymentClassWrapper)
        assert TestClass._dependencies == []
        assert TestClass._system_dependencies == []

    def test_remote_class_instantiation(self, client):
        """Test instantiating a remote class creates instance wrapper."""

        @client.remote_class()
        class TestClass:
            def __init__(self, value):
                self.value = value

            def get_value(self):
                return self.value

        instance = TestClass(42)
        assert isinstance(instance, DeploymentInstanceWrapper)
        assert instance._constructor_args == (42,)


if __name__ == "__main__":
    pytest.main([__file__])
