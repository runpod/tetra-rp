"""Tests for ManifestClient."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tetra_rp.runtime.manifest_client import (
    ManifestClient,
    ManifestServiceUnavailableError,
)


class TestManifestClient:
    """Test ManifestClient functionality."""

    @pytest.fixture
    def mock_response(self):
        """Mock successful HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "directory": {
                "gpu_config": "https://api.runpod.io/v2/gpu123",
                "cpu_config": "https://api.runpod.io/v2/cpu456",
            },
            "updated_at": "2025-01-03T12:00:00Z",
        }
        return response

    def test_init_with_url(self):
        """Test initialization with explicit URL."""
        client = ManifestClient(mothership_url="https://mothership.example.com")
        assert client.mothership_url == "https://mothership.example.com"

    def test_init_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"FLASH_MOTHERSHIP_ID": "mothership123"}):
            client = ManifestClient()
            assert client.mothership_url == "https://mothership123.api.runpod.ai"

    def test_init_missing_url(self):
        """Test initialization fails without URL."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="mothership_url required"):
                ManifestClient()

    def test_init_explicit_over_env(self):
        """Test explicit URL takes precedence over env var."""
        with patch.dict(os.environ, {"FLASH_MOTHERSHIP_ID": "env-mothership"}):
            client = ManifestClient(mothership_url="https://explicit.com")
            assert client.mothership_url == "https://explicit.com"

    @pytest.mark.asyncio
    async def test_get_directory_success(self, mock_response):
        """Test successful directory fetch."""
        client = ManifestClient(mothership_url="https://mothership.example.com")

        with patch("tetra_rp.runtime.manifest_client.httpx"):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            with patch.object(client, "_get_client", return_value=mock_client):
                directory = await client.get_directory()

                assert directory == {
                    "gpu_config": "https://api.runpod.io/v2/gpu123",
                    "cpu_config": "https://api.runpod.io/v2/cpu456",
                }

    @pytest.mark.asyncio
    async def test_get_directory_http_error(self):
        """Test handling of HTTP errors."""
        client = ManifestClient(mothership_url="https://mothership.example.com")

        response = MagicMock()
        response.status_code = 500
        response.text = "Internal server error"

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = response
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with pytest.raises(ManifestServiceUnavailableError, match="500"):
                await client.get_directory()

    @pytest.mark.asyncio
    async def test_get_directory_timeout(self):
        """Test handling of request timeout."""
        client = ManifestClient(
            mothership_url="https://mothership.example.com", timeout=0.1
        )

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.side_effect = asyncio.TimeoutError("Timed out")
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with pytest.raises(
                ManifestServiceUnavailableError, match="after \\d+ attempts"
            ):
                await client.get_directory()

    @pytest.mark.asyncio
    async def test_get_directory_retry(self):
        """Test retry logic on transient failure."""
        client = ManifestClient(
            mothership_url="https://mothership.example.com", max_retries=3
        )

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"directory": {"gpu": "https://gpu.example.com"}}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()

            # First two calls fail, third succeeds
            mock_http_client.get.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                response,
            ]
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with patch(
                "tetra_rp.runtime.manifest_client.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                directory = await client.get_directory()
                assert directory == {"gpu": "https://gpu.example.com"}
                assert mock_http_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_get_directory_exhaust_retries(self):
        """Test failure after exhausting retries."""
        client = ManifestClient(
            mothership_url="https://mothership.example.com", max_retries=2
        )

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.side_effect = Exception("Always fails")
            mock_http_client.is_closed = False
            mock_get_client.return_value = mock_http_client

            with patch(
                "tetra_rp.runtime.manifest_client.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                with pytest.raises(
                    ManifestServiceUnavailableError, match="after 2 attempts"
                ):
                    await client.get_directory()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        client = ManifestClient(mothership_url="https://mothership.example.com")

        with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
            async with client:
                pass

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test proper cleanup of HTTP client."""
        client = ManifestClient(mothership_url="https://mothership.example.com")

        with patch("tetra_rp.runtime.manifest_client.httpx"):
            mock_http_client = AsyncMock()
            mock_http_client.is_closed = False

            with patch.object(client, "_get_client", return_value=mock_http_client):
                client._client = mock_http_client
                await client.close()

                mock_http_client.aclose.assert_called_once()
