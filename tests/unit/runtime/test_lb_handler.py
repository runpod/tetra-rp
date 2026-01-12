"""Unit tests for LoadBalancer handler factory."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tetra_rp.runtime.lb_handler import create_lb_handler


class TestManifestEndpoint:
    """Tests for GET /manifest endpoint."""

    @pytest.fixture(autouse=True)
    def reset_manifest_fetcher(self):
        """Reset the global manifest fetcher before each test."""
        import tetra_rp.runtime.lb_handler as lb_handler_module

        lb_handler_module._manifest_fetcher = None
        yield
        lb_handler_module._manifest_fetcher = None

    @pytest.fixture
    def sample_manifest(self):
        """Sample manifest for testing."""
        return {
            "version": "1.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "project_name": "test-app",
            "resources": {
                "gpu_config": {
                    "resource_type": "LoadBalancerSlsResource",
                    "handler_file": "handler_gpu_config.py",
                    "functions": [
                        {
                            "name": "process_image",
                            "module": "workers.gpu",
                            "is_async": True,
                            "is_class": False,
                            "http_method": "POST",
                            "http_path": "/api/process",
                        }
                    ],
                }
            },
            "function_registry": {"process_image": "gpu_config"},
            "routes": {"gpu_config": {"POST /api/process": "process_image"}},
        }

    def test_manifest_endpoint_registered_when_env_var_true(
        self, sample_manifest, monkeypatch
    ):
        """Verify /manifest endpoint exists when FLASH_IS_MOTHERSHIP=true."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            routes = [route.path for route in app.routes]

            assert "/manifest" in routes

    def test_manifest_endpoint_not_registered_when_env_var_false(
        self, sample_manifest, monkeypatch
    ):
        """Verify /manifest endpoint doesn't exist when FLASH_IS_MOTHERSHIP=false."""
        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "false")

        app = create_lb_handler({}, include_execute=False)
        routes = [route.path for route in app.routes]

        assert "/manifest" not in routes

    def test_manifest_endpoint_not_registered_when_env_var_missing(
        self, sample_manifest
    ):
        """Verify /manifest endpoint doesn't exist when env var not set."""
        app = create_lb_handler({}, include_execute=False)
        client = TestClient(app)

        response = client.get("/manifest")
        assert response.status_code == 404

    def test_manifest_endpoint_returns_200_with_valid_manifest(
        self, sample_manifest, monkeypatch
    ):
        """Test happy path - endpoint returns 200 with valid manifest."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            assert response.status_code == 200
            assert response.json() == sample_manifest

    def test_manifest_endpoint_returns_404_when_manifest_missing(self, monkeypatch):
        """Test endpoint returns 404 when manifest file not found."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value={})
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            assert response.status_code == 404
            data = response.json()
            assert data["error"] == "Manifest not found"
            assert "Could not load" in data["detail"]

    def test_manifest_endpoint_case_insensitive_env_var_true(
        self, sample_manifest, monkeypatch
    ):
        """Test endpoint registration with different case variations of 'true'."""
        from unittest.mock import AsyncMock

        for env_value in ["True", "TRUE", "TrUe"]:
            monkeypatch.setenv("FLASH_IS_MOTHERSHIP", env_value)

            with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
                mock_fetcher = AsyncMock()
                mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
                MockFetcher.return_value = mock_fetcher

                app = create_lb_handler({}, include_execute=False)
                routes = [route.path for route in app.routes]

                assert "/manifest" in routes

    def test_manifest_endpoint_case_insensitive_env_var_false(self, monkeypatch):
        """Test endpoint not registered with non-'true' values."""
        for env_value in ["False", "false", "yes", "1", ""]:
            monkeypatch.setenv("FLASH_IS_MOTHERSHIP", env_value)

            app = create_lb_handler({}, include_execute=False)
            routes = [route.path for route in app.routes]

            assert "/manifest" not in routes

    def test_manifest_endpoint_response_structure(self, sample_manifest, monkeypatch):
        """Test that manifest response has correct structure."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")
            data = response.json()

            # Verify structure
            assert "version" in data
            assert "generated_at" in data
            assert "project_name" in data
            assert "resources" in data
            assert "function_registry" in data

    def test_manifest_endpoint_with_empty_resources(self, monkeypatch):
        """Test endpoint behavior when manifest has no resources."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        empty_manifest = {
            "version": "1.0",
            "project_name": "test",
            "resources": {},
            "function_registry": {},
        }

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=empty_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            # Should return 404 if no resources
            assert response.status_code == 404

    def test_manifest_endpoint_with_none_manifest(self, monkeypatch):
        """Test endpoint behavior when get_manifest returns None."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=None)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            assert response.status_code == 404

    def test_manifest_endpoint_coexists_with_execute(
        self, sample_manifest, monkeypatch
    ):
        """Test that /manifest endpoint coexists with /execute endpoint."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=True)
            routes = [route.path for route in app.routes]

            assert "/manifest" in routes
            assert "/execute" in routes

    def test_manifest_endpoint_coexists_with_user_routes(
        self, sample_manifest, monkeypatch
    ):
        """Test that /manifest endpoint coexists with user-defined routes."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        async def dummy_handler():
            return {"result": "ok"}

        route_registry = {("GET", "/api/health"): dummy_handler}

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler(route_registry, include_execute=False)
            routes = [route.path for route in app.routes]

            assert "/manifest" in routes
            assert "/api/health" in routes

    def test_manifest_endpoint_content_type(self, sample_manifest, monkeypatch):
        """Test that /manifest endpoint returns proper JSON content-type."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            assert response.headers["content-type"] == "application/json"

    def test_manifest_endpoint_with_complex_manifest(self, monkeypatch):
        """Test endpoint with complex multi-resource manifest."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        complex_manifest = {
            "version": "1.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "project_name": "complex-app",
            "resources": {
                "gpu_config": {
                    "resource_type": "LoadBalancerSlsResource",
                    "handler_file": "handler_gpu.py",
                    "functions": [
                        {
                            "name": "process_gpu",
                            "module": "workers.gpu",
                            "is_async": True,
                            "is_class": False,
                        }
                    ],
                },
                "cpu_config": {
                    "resource_type": "ServerlessEndpoint",
                    "handler_file": "handler_cpu.py",
                    "functions": [
                        {
                            "name": "process_cpu",
                            "module": "workers.cpu",
                            "is_async": True,
                            "is_class": False,
                        }
                    ],
                },
            },
            "function_registry": {
                "process_gpu": "gpu_config",
                "process_cpu": "cpu_config",
            },
        }

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=complex_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            response = client.get("/manifest")

            assert response.status_code == 200
            data = response.json()
            assert len(data["resources"]) == 2
            assert "gpu_config" in data["resources"]
            assert "cpu_config" in data["resources"]

    def test_manifest_endpoint_uses_fetcher_with_caching(
        self, sample_manifest, monkeypatch
    ):
        """Verify GET /manifest uses ManifestFetcher with caching."""
        from unittest.mock import AsyncMock

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=sample_manifest)
            MockFetcher.return_value = mock_fetcher

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            # First request
            response1 = client.get("/manifest")
            assert response1.status_code == 200
            assert response1.json() == sample_manifest

            # Second request - should reuse fetcher
            response2 = client.get("/manifest")
            assert response2.status_code == 200

            # Verify fetcher was called (once per request)
            assert mock_fetcher.get_manifest.call_count == 2


class TestExecuteEndpointStillWorks:
    """Tests to ensure /execute endpoint still works after manifest changes."""

    def test_execute_endpoint_still_available_with_live_load_balancer(self):
        """Verify /execute endpoint is still registered for LiveLoadBalancer."""
        app = create_lb_handler({}, include_execute=True)
        routes = [route.path for route in app.routes]

        assert "/execute" in routes

    def test_execute_endpoint_not_included_for_deployed(self):
        """Verify /execute endpoint is not registered for deployed LoadBalancer."""
        app = create_lb_handler({}, include_execute=False)
        routes = [route.path for route in app.routes]

        assert "/execute" not in routes
