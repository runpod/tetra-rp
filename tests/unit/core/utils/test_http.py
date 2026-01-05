"""Tests for HTTP utilities for RunPod API communication."""

from tetra_rp.core.utils.http import get_authenticated_httpx_client


class TestGetAuthenticatedHttpxClient:
    """Test the get_authenticated_httpx_client utility function."""

    def test_get_authenticated_httpx_client_with_api_key(self, monkeypatch):
        """Test client includes auth header when API key is set."""
        monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key-123")

        client = get_authenticated_httpx_client()

        assert client is not None
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Bearer test-api-key-123"

    def test_get_authenticated_httpx_client_without_api_key(self, monkeypatch):
        """Test client works without API key (no auth header)."""
        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

        client = get_authenticated_httpx_client()

        assert client is not None
        assert "Authorization" not in client.headers

    def test_get_authenticated_httpx_client_custom_timeout(self, monkeypatch):
        """Test client respects custom timeout."""
        monkeypatch.setenv("RUNPOD_API_KEY", "test-key")

        client = get_authenticated_httpx_client(timeout=60.0)

        assert client is not None
        assert client.timeout.read == 60.0

    def test_get_authenticated_httpx_client_default_timeout(self, monkeypatch):
        """Test client uses default timeout when not specified."""
        monkeypatch.setenv("RUNPOD_API_KEY", "test-key")

        client = get_authenticated_httpx_client()

        assert client is not None
        assert client.timeout.read == 30.0

    def test_get_authenticated_httpx_client_timeout_none_uses_default(
        self, monkeypatch
    ):
        """Test client uses default timeout when explicitly passed None."""
        monkeypatch.setenv("RUNPOD_API_KEY", "test-key")

        client = get_authenticated_httpx_client(timeout=None)

        assert client is not None
        assert client.timeout.read == 30.0

    def test_get_authenticated_httpx_client_empty_api_key_no_header(self, monkeypatch):
        """Test that empty API key doesn't add Authorization header."""
        monkeypatch.setenv("RUNPOD_API_KEY", "")

        client = get_authenticated_httpx_client()

        assert client is not None
        # Empty string is falsy, so no auth header should be added
        assert "Authorization" not in client.headers

    def test_get_authenticated_httpx_client_zero_timeout(self, monkeypatch):
        """Test client handles zero timeout correctly."""
        monkeypatch.setenv("RUNPOD_API_KEY", "test-key")

        client = get_authenticated_httpx_client(timeout=0.0)

        assert client is not None
        assert client.timeout.read == 0.0
