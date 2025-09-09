"""
Unit tests for LoadBalancerSls health checks and retry logic.

Tests the health check functionality in LoadBalancerSls client, including
automatic health checks before requests, manual health checks, retry logic,
and progressive backoff behavior.
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import Mock, AsyncMock, patch

from tetra_rp.core.resources.load_balancer_sls.client import LoadBalancerSls
from tetra_rp.core.resources.load_balancer_sls.exceptions import (
    LoadBalancerSlsConnectionError,
    LoadBalancerSlsError,
)


class TestLoadBalancerSlsHealthCheck:
    """Test LoadBalancerSls health check functionality."""

    @pytest.fixture
    def client(self):
        """Create LoadBalancerSls client for testing."""
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai",
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
            retry_delay=0.1,  # Fast retries for tests
        )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        with patch.object(client, "_make_request_with_retry") as mock_request:
            mock_request.return_value = {
                "status": "healthy",
                "timestamp": "2023-01-01T00:00:00Z",
            }

            result = await client.health_check()

            mock_request.assert_called_once_with(
                "GET", f"{client.endpoint_url}/health", "health_check"
            )
            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client):
        """Test health check with connection error."""
        with patch.object(client, "_make_request_with_retry") as mock_request:
            mock_request.side_effect = LoadBalancerSlsConnectionError(
                client.endpoint_url, "Connection failed", {}
            )

            with pytest.raises(LoadBalancerSlsConnectionError):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_health_check_unexpected_error(self, client):
        """Test health check with unexpected error."""
        with patch.object(client, "_make_request_with_retry") as mock_request:
            mock_request.side_effect = ValueError("Unexpected error")

            with pytest.raises(
                LoadBalancerSlsError, match="Unexpected error during health check"
            ):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_automatic_health_check_before_remote_call(self, client):
        """Test automatic health check before remote method calls."""
        with patch.object(client, "_perform_health_check") as mock_health_check:
            with patch.object(client, "_make_request_with_retry") as mock_request:
                mock_health_check.return_value = {"status": "healthy"}
                mock_request.return_value = {"success": True, "result": "test_result"}

                from tetra_rp.protos.remote_execution import FunctionRequest

                request = FunctionRequest(
                    execution_type="function",
                    method_name="test_method",
                    args=[],
                    kwargs={},
                    dependencies=[],
                    system_dependencies=[],
                )

                await client.call_remote_method(request)

                # Should perform health check first
                mock_health_check.assert_called_once()
                # Then make the actual request
                mock_request.assert_called_once_with(
                    "POST",
                    f"{client.endpoint_url}/execute",
                    "remote_execution_test_method",
                    {"input": request.model_dump(exclude_none=True)},
                )

    @pytest.mark.asyncio
    async def test_automatic_health_check_before_http_call(self, client):
        """Test automatic health check before HTTP endpoint calls."""
        with patch.object(client, "_perform_health_check") as mock_health_check:
            with patch.object(client, "_make_request_with_retry") as mock_request:
                mock_health_check.return_value = {"status": "healthy"}
                mock_request.return_value = {"result": "http_result"}

                await client.call_http_endpoint("predict", {"data": "test"})

                # Should perform health check first
                mock_health_check.assert_called_once()
                # Then make the actual request
                mock_request.assert_called_once_with(
                    "POST",
                    f"{client.endpoint_url}/predict",
                    "http_endpoint_predict",
                    {"data": "test"},
                )

    @pytest.mark.asyncio
    async def test_health_check_skipped_after_first_success(self, client):
        """Test health check is skipped after first successful check."""
        with patch.object(client, "_perform_health_check") as mock_health_check:
            with patch.object(client, "_make_request_with_retry") as mock_request:
                mock_health_check.return_value = {"status": "healthy"}
                mock_request.return_value = {"result": "test_result"}

                # First call should perform health check
                await client.call_http_endpoint("method1", {"data": "test1"})
                assert mock_health_check.call_count == 1

                # Second call should skip health check
                await client.call_http_endpoint("method2", {"data": "test2"})
                assert mock_health_check.call_count == 1  # Still 1, not called again

    @pytest.mark.asyncio
    async def test_health_check_reset_after_failure(self, client):
        """Test health check flag is reset after connection failure."""
        with patch.object(client, "_perform_health_check") as mock_health_check:
            with patch.object(client, "_make_request_with_retry") as mock_request:
                # First call succeeds
                mock_health_check.return_value = {"status": "healthy"}
                mock_request.return_value = {"result": "success"}
                await client.call_http_endpoint("method1", {"data": "test1"})
                assert client._health_checked is True

                # Simulate connection failure that would reset health check flag
                client._health_checked = False

                # Next call should perform health check again
                await client.call_http_endpoint("method2", {"data": "test2"})
                assert mock_health_check.call_count == 2


class TestLoadBalancerSlsHealthCheckRetry:
    """Test LoadBalancerSls health check retry logic."""

    @pytest.fixture
    def client(self):
        """Create LoadBalancerSls client with specific retry settings."""
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai",
            api_key="test-key",
            timeout=30.0,
            max_retries=1,
            retry_delay=0.05,  # Very fast for tests
        )

    @pytest.mark.asyncio
    async def test_health_check_retry_success_on_second_attempt(self, client):
        """Test health check succeeds on retry."""
        call_count = 0

        def mock_perform_health_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise aiohttp.ClientError("First attempt fails")
            return {"status": "healthy"}

        with patch.object(
            client, "_perform_health_check", side_effect=mock_perform_health_check
        ):
            with patch(
                "asyncio.sleep", new_callable=AsyncMock
            ):  # Mock sleep for fast tests
                # This should call _ensure_healthy internally
                with patch.object(client, "_make_request_with_retry") as mock_request:
                    mock_request.return_value = {"result": "success"}

                    await client.call_http_endpoint("test", {})

                    # Health check should have been called twice (once failed, once succeeded)
                    assert call_count == 2
                    assert client._health_checked is True

    @pytest.mark.asyncio
    async def test_health_check_retry_progressive_backoff(self, client):
        """Test health check uses progressive backoff."""
        sleep_times = []

        async def mock_sleep(time):
            sleep_times.append(time)

        with patch.object(
            client, "_perform_health_check", side_effect=Exception("Always fails")
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(LoadBalancerSlsConnectionError):
                    await client._ensure_healthy()

                # Should have progressive backoff: 1.0, 2.0, 3.0 seconds
                assert (
                    len(sleep_times) == 2
                )  # 3 attempts - 1 (no sleep before first attempt)
                assert sleep_times[0] == 1.0
                assert sleep_times[1] == 2.0

    @pytest.mark.asyncio
    async def test_health_check_max_retries_exhausted(self, client):
        """Test health check fails after max retries."""
        call_count = 0

        def failing_health_check():
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientError(f"Attempt {call_count} failed")

        with patch.object(
            client, "_perform_health_check", side_effect=failing_health_check
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(
                    LoadBalancerSlsConnectionError,
                    match="Endpoint health check failed after 3 attempts",
                ):
                    await client._ensure_healthy()

                # Should have tried 3 times (initial + 2 retries based on _health_check_retries)
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_health_check_error_details_in_exception(self, client):
        """Test health check exception includes proper error details."""
        error_msg = "Specific connection error"

        with patch.object(
            client, "_perform_health_check", side_effect=Exception(error_msg)
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                try:
                    await client._ensure_healthy()
                except LoadBalancerSlsConnectionError as e:
                    assert client.endpoint_url in str(e)
                    assert "3 attempts" in str(e)  # Should mention retry count
                    assert error_msg in str(e)
                    assert e.context["attempts"] == 3
                    assert error_msg in e.context["last_error"]
                else:
                    pytest.fail("Expected LoadBalancerSlsConnectionError")


class TestLoadBalancerSlsRequestRetry:
    """Test LoadBalancerSls request-level retry logic."""

    @pytest.fixture
    def client(self):
        """Create LoadBalancerSls client with retry settings."""
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai",
            api_key="test-key",
            max_retries=2,
            retry_delay=0.05,  # Fast for tests
        )

    @pytest.mark.asyncio
    async def test_request_retry_exponential_backoff(self, client):
        """Test request retry uses exponential backoff."""
        sleep_times = []

        async def mock_sleep(time):
            sleep_times.append(time)

        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.post.side_effect = aiohttp.ClientError("Connection failed")
            mock_session.__aenter__.return_value = mock_response
            mock_get_session.return_value.post.side_effect = aiohttp.ClientError(
                "Connection failed"
            )

            with patch("asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(LoadBalancerSlsConnectionError):
                    await client._make_request_with_retry(
                        "POST",
                        f"{client.endpoint_url}/test",
                        "test_operation",
                        {"data": "test"},
                    )

                # Should have exponential backoff: 0.05, 0.1 (retry_delay * 2^attempt)
                assert len(sleep_times) == 2  # 3 attempts - 1
                assert sleep_times[0] == 0.05  # 0.05 * 2^0
                assert sleep_times[1] == 0.1  # 0.05 * 2^1

    @pytest.mark.asyncio
    async def test_request_retry_success_on_retry(self, client):
        """Test request succeeds on retry."""
        attempt_count = 0

        async def mock_session_request(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise aiohttp.ClientError("First attempt fails")
            # Return a mock response for second attempt
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"success": True})
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = Mock()
            mock_session.post.side_effect = mock_session_request
            mock_get_session.return_value = mock_session

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._make_request_with_retry(
                    "POST",
                    f"{client.endpoint_url}/test",
                    "test_operation",
                    {"data": "test"},
                )

                assert result == {"success": True}
                assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_request_retry_different_errors(self, client):
        """Test request retry handles different types of errors."""
        errors = [
            aiohttp.ClientError("Client error"),
            asyncio.TimeoutError("Timeout error"),
            aiohttp.ServerConnectionError("Server connection error"),
        ]

        attempt_count = 0

        async def mock_failing_request(*args, **kwargs):
            nonlocal attempt_count
            if attempt_count < len(errors):
                error = errors[attempt_count]
                attempt_count += 1
                raise error
            # Final attempt succeeds
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"success": True})
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = Mock()
            mock_session.post.side_effect = mock_failing_request
            mock_get_session.return_value = mock_session

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._make_request_with_retry(
                    "POST",
                    f"{client.endpoint_url}/test",
                    "test_operation",
                    {"data": "test"},
                )

                assert result == {"success": True}
                assert attempt_count == len(errors)  # All errors tried

    @pytest.mark.asyncio
    async def test_request_no_retry_on_auth_error(self, client):
        """Test request doesn't retry on authentication errors."""
        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status = 401
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()
            mock_session.post.return_value = mock_response
            mock_get_session.return_value = mock_session

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with pytest.raises(Exception):  # Should raise before retries
                    await client._make_request_with_retry(
                        "POST",
                        f"{client.endpoint_url}/test",
                        "test_operation",
                        {"data": "test"},
                    )

                # Should not have slept (no retries)
                mock_sleep.assert_not_called()


class TestLoadBalancerSlsHealthCheckIntegration:
    """Test integration between health checks and regular operations."""

    @pytest.fixture
    def client(self):
        """Create LoadBalancerSls client for integration testing."""
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai",
            api_key="test-key",
            timeout=30.0,
            max_retries=1,
            retry_delay=0.05,
        )

    @pytest.mark.asyncio
    async def test_failed_health_check_blocks_operations(self, client):
        """Test failed health check blocks subsequent operations."""
        with patch.object(
            client,
            "_perform_health_check",
            side_effect=Exception("Health check failed"),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Both remote and HTTP calls should fail due to health check
                with pytest.raises(LoadBalancerSlsConnectionError):
                    await client.call_http_endpoint("test", {})

                from tetra_rp.protos.remote_execution import FunctionRequest

                request = FunctionRequest(
                    execution_type="function", method_name="test", args=[], kwargs={}
                )

                with pytest.raises(LoadBalancerSlsConnectionError):
                    await client.call_remote_method(request)

    @pytest.mark.asyncio
    async def test_health_check_state_persists_across_calls(self, client):
        """Test health check state persists across multiple calls."""
        health_check_count = 0

        def mock_health_check():
            nonlocal health_check_count
            health_check_count += 1
            return {"status": "healthy"}

        with patch.object(
            client, "_perform_health_check", side_effect=mock_health_check
        ):
            with patch.object(client, "_make_request_with_retry") as mock_request:
                mock_request.return_value = {"success": True}

                # Make multiple calls
                await client.call_http_endpoint("method1", {})
                await client.call_http_endpoint("method2", {})
                await client.call_http_endpoint("method3", {})

                # Health check should only be called once
                assert health_check_count == 1
                # But actual requests should be made multiple times
                assert mock_request.call_count == 3
