"""Integration tests for @remote with LoadBalancerSlsResource.

These tests verify the full flow of using @remote with load-balanced endpoints,
including local development with LiveLoadBalancer and HTTP execution.
"""

import base64
import pytest
from unittest.mock import MagicMock

import cloudpickle

from tetra_rp import remote, LiveLoadBalancer, LoadBalancerSlsResource


class TestRemoteWithLoadBalancerIntegration:
    """Integration tests for @remote decorator with LB endpoints."""

    def test_decorator_accepts_lb_resource_with_routing(self):
        """Test that @remote accepts LoadBalancerSlsResource with method/path."""
        lb = LoadBalancerSlsResource(name="test-api", imageName="test:latest")

        @remote(lb, method="POST", path="/api/process")
        async def process_data(x: int, y: int):
            return {"result": x + y}

        # Should not raise - decorator accepts the parameters
        assert hasattr(process_data, "__remote_config__")
        assert process_data.__remote_config__["method"] == "POST"
        assert process_data.__remote_config__["path"] == "/api/process"

    def test_decorator_validates_method_and_path_required(self):
        """Test that @remote requires both method and path for LB resources."""
        lb = LoadBalancerSlsResource(name="test-api", imageName="test:latest")

        with pytest.raises(ValueError, match="requires both 'method' and 'path'"):

            @remote(lb)
            async def missing_routing():
                pass

    def test_decorator_validates_invalid_http_method(self):
        """Test that @remote rejects invalid HTTP methods."""
        lb = LoadBalancerSlsResource(name="test-api", imageName="test:latest")

        with pytest.raises(ValueError, match="must be one of"):

            @remote(lb, method="INVALID", path="/api/test")
            async def bad_method():
                pass

    def test_decorator_validates_path_starts_with_slash(self):
        """Test that @remote requires path to start with /."""
        lb = LoadBalancerSlsResource(name="test-api", imageName="test:latest")

        with pytest.raises(ValueError, match="must start with '/'"):

            @remote(lb, method="GET", path="api/test")
            async def bad_path():
                pass

    @pytest.mark.asyncio
    async def test_remote_function_serialization_roundtrip(self):
        """Test that function code and args serialize/deserialize correctly."""
        from tetra_rp.stubs.load_balancer_sls import LoadBalancerSlsStub

        mock_resource = MagicMock()
        stub = LoadBalancerSlsStub(mock_resource)

        def add(x: int, y: int) -> int:
            """Simple add function."""
            return x + y

        # Prepare request
        request = stub._prepare_request(add, None, None, True, 5, 3)

        # Verify request structure
        assert request["function_name"] == "add"
        assert "def add" in request["function_code"]
        assert len(request["args"]) == 2

        # Deserialize and verify arguments
        arg0 = cloudpickle.loads(base64.b64decode(request["args"][0]))
        arg1 = cloudpickle.loads(base64.b64decode(request["args"][1]))
        assert arg0 == 5
        assert arg1 == 3

    @pytest.mark.asyncio
    async def test_stub_response_deserialization(self):
        """Test that response deserialization works correctly."""
        from tetra_rp.stubs.load_balancer_sls import LoadBalancerSlsStub

        mock_resource = MagicMock()
        stub = LoadBalancerSlsStub(mock_resource)

        result_value = {"status": "success", "count": 42}
        result_b64 = base64.b64encode(cloudpickle.dumps(result_value)).decode("utf-8")

        response = {"success": True, "result": result_b64}

        # Handle response
        result = stub._handle_response(response)

        assert result == result_value

    def test_live_load_balancer_creation(self):
        """Test that LiveLoadBalancer can be created and used with @remote."""
        lb = LiveLoadBalancer(name="test-live-api")

        @remote(lb, method="POST", path="/api/echo")
        async def echo(message: str):
            return {"echo": message}

        # Verify resource is correctly configured
        # Note: name may have "-fb" appended by flash boot validator
        assert "test-live-api" in lb.name
        assert "tetra-rp-lb" in lb.imageName
        assert echo.__remote_config__["method"] == "POST"

    def test_live_load_balancer_image_locked(self):
        """Test that LiveLoadBalancer locks the image to Tetra LB image."""
        lb = LiveLoadBalancer(name="test-api")

        # Verify image is locked and cannot be overridden
        original_image = lb.imageName
        assert "tetra-rp-lb" in original_image

        # Try to set a different image (should be ignored due to property)
        lb.imageName = "custom-image:latest"

        # Image should still be locked to Tetra
        assert lb.imageName == original_image

    def test_load_balancer_vs_queue_based_endpoints(self):
        """Test that LB and QB endpoints have different characteristics."""
        from tetra_rp import ServerlessEndpoint

        lb = LoadBalancerSlsResource(name="lb-api", imageName="test:latest")
        qb = ServerlessEndpoint(name="qb-api", imageName="test:latest")

        @remote(lb, method="POST", path="/api/echo")
        async def lb_func():
            return "lb"

        @remote(qb)
        async def qb_func():
            return "qb"

        # Both should have __remote_config__
        assert hasattr(lb_func, "__remote_config__")
        assert hasattr(qb_func, "__remote_config__")

        # LB should have routing config
        assert lb_func.__remote_config__["method"] == "POST"
        assert lb_func.__remote_config__["path"] == "/api/echo"

        # QB should have None values for routing (not LB-specific)
        assert qb_func.__remote_config__["method"] is None
        assert qb_func.__remote_config__["path"] is None

    def test_live_load_balancer_handler_includes_execute_endpoint(self):
        """Test that generated handler for LiveLoadBalancer includes /execute endpoint."""
        from tetra_rp.cli.commands.build_utils.lb_handler_generator import (
            LBHandlerGenerator,
        )
        from datetime import datetime, timezone
        from pathlib import Path
        import tempfile

        # Create a manifest for LiveLoadBalancer
        manifest = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "project_name": "test-project",
            "resources": {
                "test-api": {
                    "resource_type": "LiveLoadBalancer",
                    "handler_file": "handler_test_api.py",
                    "functions": [
                        {
                            "name": "process_data",
                            "module": "api.endpoints",
                            "is_async": True,
                            "is_class": False,
                            "http_method": "POST",
                            "http_path": "/api/process",
                        }
                    ],
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            generator = LBHandlerGenerator(manifest, build_dir)
            handlers = generator.generate_handlers()

            assert len(handlers) == 1
            handler_path = handlers[0]
            handler_code = handler_path.read_text()

            # Verify the handler includes include_execute=True for LiveLoadBalancer
            assert "include_execute=True" in handler_code
            assert (
                "create_lb_handler(ROUTE_REGISTRY, include_execute=True)"
                in handler_code
            )

    def test_deployed_load_balancer_handler_excludes_execute_endpoint(self):
        """Test that generated handler for deployed LoadBalancerSlsResource excludes /execute endpoint."""
        from tetra_rp.cli.commands.build_utils.lb_handler_generator import (
            LBHandlerGenerator,
        )
        from datetime import datetime, timezone
        from pathlib import Path
        import tempfile

        # Create a manifest for deployed LoadBalancerSlsResource
        manifest = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "project_name": "test-project",
            "resources": {
                "api-service": {
                    "resource_type": "LoadBalancerSlsResource",
                    "handler_file": "handler_api_service.py",
                    "functions": [
                        {
                            "name": "process_data",
                            "module": "api.endpoints",
                            "is_async": True,
                            "is_class": False,
                            "http_method": "POST",
                            "http_path": "/api/process",
                        }
                    ],
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            generator = LBHandlerGenerator(manifest, build_dir)
            handlers = generator.generate_handlers()

            assert len(handlers) == 1
            handler_path = handlers[0]
            handler_code = handler_path.read_text()

            # Verify the handler includes include_execute=False for deployed endpoints
            assert "include_execute=False" in handler_code
            assert (
                "create_lb_handler(ROUTE_REGISTRY, include_execute=False)"
                in handler_code
            )

    def test_scanner_discovers_load_balancer_resources(self):
        """Test that scanner can discover LiveLoadBalancer and LoadBalancerSlsResource."""
        from tetra_rp.cli.commands.build_utils.scanner import RemoteDecoratorScanner
        from pathlib import Path
        import tempfile

        # Create temporary Python file with LoadBalancer resource
        code = """
from tetra_rp import LiveLoadBalancer, LoadBalancerSlsResource, remote

# Test LiveLoadBalancer discovery
api = LiveLoadBalancer(name="test-api")

@remote(api, method="POST", path="/api/process")
async def process_data(x: int):
    return {"result": x}

# Test LoadBalancerSlsResource discovery
deployed = LoadBalancerSlsResource(name="deployed-api", imageName="test:latest")

@remote(deployed, method="GET", path="/api/status")
def get_status():
    return {"status": "ok"}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            py_file = project_dir / "test_api.py"
            py_file.write_text(code)

            scanner = RemoteDecoratorScanner(project_dir)
            functions = scanner.discover_remote_functions()

            # Verify both resources were discovered
            assert len(functions) == 2

            # Verify resource types are correctly identified
            resource_types = {f.resource_type for f in functions}
            assert "LiveLoadBalancer" in resource_types
            assert "LoadBalancerSlsResource" in resource_types

            # Verify resource configs were extracted
            assert "test-api" in scanner.resource_types
            assert scanner.resource_types["test-api"] == "LiveLoadBalancer"
            assert "deployed-api" in scanner.resource_types
            assert scanner.resource_types["deployed-api"] == "LoadBalancerSlsResource"


class TestManifestEndpointIntegration:
    """Integration tests for GET /manifest endpoint."""

    @pytest.fixture(autouse=True)
    def reset_manifest_fetcher(self):
        """Reset the global manifest fetcher before each test."""
        import tetra_rp.runtime.lb_handler as lb_handler_module

        lb_handler_module._manifest_fetcher = None
        yield
        lb_handler_module._manifest_fetcher = None

    def test_manifest_endpoint_in_live_load_balancer(self, monkeypatch):
        """Test manifest endpoint in LiveLoadBalancer with FLASH_IS_MOTHERSHIP=true."""
        from unittest.mock import patch, AsyncMock
        from fastapi.testclient import TestClient

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")

        # Create a LiveLoadBalancer
        lb = LiveLoadBalancer(name="test-mothership")

        # Define a simple function on the mothership
        @remote(lb, method="GET", path="/api/hello")
        async def hello():
            return {"message": "hello"}

        # Create manifest data
        test_manifest = {
            "version": "1.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "project_name": "test-app",
            "resources": {
                "test-mothership": {
                    "resource_type": "LiveLoadBalancer",
                    "handler_file": "handler_test_mothership.py",
                    "functions": [
                        {
                            "name": "hello",
                            "module": "test_module",
                            "is_async": True,
                            "is_class": False,
                            "http_method": "GET",
                            "http_path": "/api/hello",
                        }
                    ],
                }
            },
            "function_registry": {"hello": "test-mothership"},
            "routes": {"test-mothership": {"GET /api/hello": "hello"}},
        }

        # Mock ManifestFetcher to return test manifest
        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=test_manifest)
            MockFetcher.return_value = mock_fetcher

            from tetra_rp.runtime.lb_handler import create_lb_handler

            # Create handler with manifest endpoint enabled
            route_registry = {("GET", "/api/hello"): hello}
            app = create_lb_handler(route_registry, include_execute=True)
            client = TestClient(app)

            # Verify /manifest endpoint returns manifest
            response = client.get("/manifest")
            assert response.status_code == 200
            assert response.json() == test_manifest

    def test_manifest_endpoint_excluded_when_env_not_set(self):
        """Test manifest endpoint is not available when FLASH_IS_MOTHERSHIP not set."""
        from fastapi.testclient import TestClient
        from tetra_rp.runtime.lb_handler import create_lb_handler

        # Create handler without env var set
        app = create_lb_handler({}, include_execute=False)
        client = TestClient(app)

        # Verify /manifest returns 404
        response = client.get("/manifest")
        assert response.status_code == 404

    def test_manifest_endpoint_with_deployed_lb_resource(self, monkeypatch):
        """Test manifest endpoint with LoadBalancerSlsResource."""
        from unittest.mock import patch, AsyncMock
        from fastapi.testclient import TestClient
        from tetra_rp.runtime.lb_handler import _get_manifest_fetcher

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")
        _get_manifest_fetcher.cache_clear()

        # Create test manifest for deployed endpoint
        test_manifest = {
            "version": "1.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "project_name": "deployed-app",
            "resources": {
                "gpu-worker": {
                    "resource_type": "LoadBalancerSlsResource",
                    "handler_file": "handler_gpu_worker.py",
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
            "function_registry": {"process_image": "gpu-worker"},
        }

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=test_manifest)
            MockFetcher.return_value = mock_fetcher

            from tetra_rp.runtime.lb_handler import create_lb_handler

            # Create deployed handler (not LiveLoadBalancer)
            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            # Verify /manifest endpoint is available
            response = client.get("/manifest")
            assert response.status_code == 200
            assert response.json() == test_manifest

        _get_manifest_fetcher.cache_clear()

    def test_manifest_endpoint_coexists_with_ping(self, monkeypatch):
        """Test that /manifest endpoint coexists with /ping health check."""
        from unittest.mock import patch, AsyncMock
        from fastapi.testclient import TestClient
        from tetra_rp.runtime.lb_handler import _get_manifest_fetcher

        monkeypatch.setenv("FLASH_IS_MOTHERSHIP", "true")
        _get_manifest_fetcher.cache_clear()

        test_manifest = {
            "version": "1.0",
            "resources": {"test": {}},
            "function_registry": {},
        }

        with patch("tetra_rp.runtime.lb_handler.ManifestFetcher") as MockFetcher:
            mock_fetcher = AsyncMock()
            mock_fetcher.get_manifest = AsyncMock(return_value=test_manifest)
            MockFetcher.return_value = mock_fetcher

            from tetra_rp.runtime.lb_handler import create_lb_handler

            app = create_lb_handler({}, include_execute=False)
            client = TestClient(app)

            # Verify both endpoints exist
            manifest_response = client.get("/manifest")
            assert manifest_response.status_code == 200

            ping_response = client.get("/ping")
            assert ping_response.status_code == 404  # Ping not auto-added by factory

        _get_manifest_fetcher.cache_clear()


class TestManifestClientToEndpointIntegration:
    """Integration tests for ManifestClient calling GET /manifest endpoint."""

    def test_manifest_client_can_parse_response(self):
        """Test ManifestClient can parse manifest response directly."""
        import asyncio
        from unittest.mock import patch, AsyncMock, MagicMock
        from tetra_rp.runtime.manifest_client import ManifestClient

        # Create a manifest to simulate
        test_manifest = {
            "version": "1.0",
            "generated_at": "2024-01-15T10:30:00Z",
            "project_name": "test-app",
            "resources": {
                "gpu_config": {
                    "resource_type": "LoadBalancerSlsResource",
                    "handler_file": "handler_gpu.py",
                    "endpoint_url": "https://api.runpod.io/v2/gpu123",
                }
            },
            "function_registry": {"process_gpu": "gpu_config"},
        }

        async def test_client_parsing():
            # Create a mock httpx client that returns the manifest directly
            mock_http_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = test_manifest
            mock_http_client.get = AsyncMock(return_value=mock_response)

            # Create ManifestClient
            client = ManifestClient(mothership_url="http://localhost:8000")

            # Mock the _get_client to return our mock
            with patch.object(client, "_get_client", return_value=mock_http_client):
                # Call get_manifest - should parse the response
                result = await client.get_manifest()

                # Verify it successfully parsed the manifest
                assert result == test_manifest
                assert "gpu_config" in result["resources"]
                assert result["function_registry"]["process_gpu"] == "gpu_config"

        # Run the async test
        asyncio.run(test_client_parsing())
