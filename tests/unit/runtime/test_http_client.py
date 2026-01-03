"""Tests for CrossEndpointClient."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tetra_rp.runtime.http_client import CrossEndpointClient


class TestCrossEndpointClient:
    """Test CrossEndpointClient functionality."""

    @pytest.fixture
    def client(self):
        """Create client with test config."""
        return CrossEndpointClient(
            timeout=10,
            poll_interval=0.01,  # Short interval for tests
            max_polls=100,
            api_key="test-key",
        )

    @pytest.fixture
    def sample_payload(self):
        """Sample RunPod-format payload."""
        return {
            "input": {
                "function_name": "gpu_task",
                "execution_type": "function",
                "args": ["base64_arg1"],
                "kwargs": {"key": "base64_val"},
            }
        }

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        client = CrossEndpointClient(api_key="my-key")
        assert client.api_key == "my-key"

    def test_init_from_env(self):
        """Test initialization from RUNPOD_API_KEY env var."""
        import os

        with patch.dict(os.environ, {"RUNPOD_API_KEY": "env-key"}):
            client = CrossEndpointClient()
            assert client.api_key == "env-key"

    def test_init_timeout_and_polling(self):
        """Test timeout and polling configuration."""
        client = CrossEndpointClient(timeout=600, poll_interval=2, max_polls=100)
        assert client.timeout == 600
        assert client.poll_interval == 2
        assert client.max_polls == 100

    @pytest.mark.asyncio
    async def test_execute_sync_success(self, client, sample_payload):
        """Test synchronous execution success."""
        response_data = {
            "success": True,
            "result": base64.b64encode(b"pickled_result").decode("utf-8"),
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = response_data

            mock_http_client.post.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with patch("tetra_rp.runtime.http_client.cloudpickle") as mock_pickle:
                mock_pickle.loads.return_value = "deserialized_result"

                result = await client.execute(
                    "https://endpoint.example.com",
                    sample_payload,
                    sync=True,
                )

                assert result["success"] is True
                assert result["result"] == "deserialized_result"

                # Verify sync endpoint was used
                call_args = mock_http_client.post.call_args
                assert "/runsync" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_async_with_polling(self, client, sample_payload):
        """Test asynchronous execution with job polling."""
        job_response = {"id": "job-123", "status": "IN_QUEUE"}

        poll_responses = [
            {"status": "IN_QUEUE"},
            {"status": "IN_PROGRESS"},
            {
                "status": "COMPLETED",
                "output": {
                    "success": True,
                    "result": base64.b64encode(b"pickled_result").decode("utf-8"),
                },
            },
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()

            # Initial POST response
            post_response = MagicMock()
            post_response.status_code = 200
            post_response.json.return_value = job_response

            # GET responses for polling
            get_responses = [
                MagicMock(status_code=200, json=MagicMock(return_value=r))
                for r in poll_responses
            ]

            mock_http_client.post.return_value = post_response
            mock_http_client.get.side_effect = get_responses
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with patch("tetra_rp.runtime.http_client.cloudpickle") as mock_pickle:
                mock_pickle.loads.return_value = "deserialized_result"

                result = await client.execute(
                    "https://endpoint.example.com",
                    sample_payload,
                    sync=False,
                )

                assert result["success"] is True
                assert result["result"] == "deserialized_result"

                # Verify async endpoint was used
                call_args = mock_http_client.post.call_args
                assert "/run" in call_args[0][0]
                assert "/runsync" not in call_args[0][0]

                # Verify polling happened
                assert mock_http_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_authentication(self, client, sample_payload):
        """Test that API key is sent in Authorization header."""
        response_data = {"id": "job-123"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = response_data

            mock_http_client.post.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            # Start execute (will fail on polling, but we just check headers)
            with patch.object(client, "_poll_job", new_callable=AsyncMock) as mock_poll:
                mock_poll.return_value = {"output": {"success": True, "result": None}}

                await client.execute(
                    "https://endpoint.example.com",
                    sample_payload,
                    sync=False,
                )

                # Check POST headers
                call_args = mock_http_client.post.call_args
                headers = call_args[1]["headers"]
                assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_execute_http_error(self, client, sample_payload):
        """Test handling of HTTP errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = MagicMock()
            response.status_code = 500
            response.text = "Internal server error"

            mock_http_client.post.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with pytest.raises(Exception, match="500"):
                await client.execute(
                    "https://endpoint.example.com",
                    sample_payload,
                )

    @pytest.mark.asyncio
    async def test_execute_remote_execution_error(self, client, sample_payload):
        """Test handling of remote execution errors."""
        error_response = {
            "success": False,
            "error": "Remote function failed: division by zero",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = error_response

            mock_http_client.post.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            result = await client.execute(
                "https://endpoint.example.com",
                sample_payload,
                sync=True,
            )

            assert result["success"] is False
            assert "division by zero" in result["error"]

    @pytest.mark.asyncio
    async def test_poll_job_success(self, client):
        """Test successful job polling."""
        responses = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"status": "IN_PROGRESS"}),
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(
                    return_value={
                        "status": "COMPLETED",
                        "output": {"success": True, "result": None},
                    }
                ),
            ),
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.side_effect = responses
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            result = await client._poll_job("https://endpoint.example.com", "job-123")

            assert result["status"] == "COMPLETED"
            assert mock_http_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_poll_job_timeout(self, client):
        """Test job polling timeout."""
        client.max_polls = 2
        client.poll_interval = 0.01

        response = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": "IN_PROGRESS"}),
        )

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with pytest.raises(Exception, match="did not complete within"):
                await client._poll_job("https://endpoint.example.com", "job-123")

    def test_deserialize_response_success(self, client):
        """Test result deserialization."""
        result_b64 = base64.b64encode(b"test_result").decode("utf-8")
        response = {
            "output": {
                "success": True,
                "result": result_b64,
            }
        }

        with patch("tetra_rp.runtime.http_client.cloudpickle") as mock_pickle:
            mock_pickle.loads.return_value = "deserialized"

            result = client._deserialize_response(response)

            assert result["success"] is True
            assert result["result"] == "deserialized"

    def test_deserialize_response_error(self, client):
        """Test error deserialization."""
        response = {
            "output": {
                "success": False,
                "error": "Function failed",
            }
        }

        result = client._deserialize_response(response)

        assert result["success"] is False
        assert result["error"] == "Function failed"

    def test_deserialize_response_no_result(self, client):
        """Test successful response with no result."""
        response = {
            "output": {
                "success": True,
            }
        }

        result = client._deserialize_response(response)

        assert result["success"] is True
        assert result["result"] is None

    def test_deserialize_response_direct_format(self, client):
        """Test response without 'output' wrapper."""
        result_b64 = base64.b64encode(b"test_result").decode("utf-8")
        response = {
            "success": True,
            "result": result_b64,
        }

        with patch("tetra_rp.runtime.http_client.cloudpickle") as mock_pickle:
            mock_pickle.loads.return_value = "deserialized"

            result = client._deserialize_response(response)

            assert result["success"] is True
            assert result["result"] == "deserialized"

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager."""
        with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
            async with client:
                pass

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test proper cleanup of HTTP client."""
        with patch("tetra_rp.runtime.http_client.httpx"):
            mock_http_client = AsyncMock()
            mock_http_client.is_closed = False

            with patch.object(client, "_get_client", return_value=mock_http_client):
                client._client = mock_http_client
                await client.close()

                mock_http_client.aclose.assert_called_once()
