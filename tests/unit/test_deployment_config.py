"""Unit tests for deployment configuration generation."""

import json


from tetra_rp.cli.utils.deployment_config import (
    generate_deployment_manifest,
    generate_endpoint_config,
    read_deployment_manifest,
    write_deployment_manifest,
)
from tetra_rp.cli.utils.handler_discovery import (
    DiscoveryResult,
    HandlerMetadata,
)


class TestEndpointConfigGeneration:
    """Tests for endpoint configuration generation."""

    def test_generate_gpu_endpoint_config(self):
        """Test generating GPU endpoint configuration."""
        handler = HandlerMetadata(
            handler_id="test_handler_12345678",
            handler_type="queue",
            serverless_config={
                "resource_class": "LiveServerless",
                "compute_type": "gpu",
                "serverless": {
                    "name": "test_worker",
                    "gpus": ["NVIDIA A40"],
                    "workersMin": 0,
                    "workersMax": 3,
                    "idleTimeout": 5,
                    "gpuCount": 1,
                },
            },
            routes=[
                {"path": "/hello", "method": "POST", "function": "hello", "line": 10}
            ],
            source_file="main.py",
            source_router="app",
            compute_type="gpu",
            resource_class="LiveServerless",
        )

        config = generate_endpoint_config(handler, "my-app")

        assert config["handler_id"] == "test_handler_12345678"
        assert config["handler_type"] == "queue"
        assert config["compute_type"] == "gpu"
        assert config["resource_class"] == "LiveServerless"

        endpoint_config = config["endpoint_config"]
        assert endpoint_config["name"] == "my-app-test_handler_12345678"
        assert endpoint_config["type"] == "QB"
        assert endpoint_config["workersMin"] == 0
        assert endpoint_config["workersMax"] == 3
        assert endpoint_config["idleTimeout"] == 5
        assert endpoint_config["gpus"] == ["NVIDIA A40"]
        assert endpoint_config["gpuCount"] == 1

    def test_generate_cpu_endpoint_config(self):
        """Test generating CPU endpoint configuration."""
        handler = HandlerMetadata(
            handler_id="cpu_handler_87654321",
            handler_type="load_balancer",
            serverless_config={
                "resource_class": "CpuLiveServerless",
                "compute_type": "cpu",
                "serverless": {
                    "name": "cpu_worker",
                    "instanceIds": ["cpu5g-2-8"],
                    "workersMin": 0,
                    "workersMax": 5,
                    "idleTimeout": 10,
                },
            },
            routes=[
                {
                    "path": "/process",
                    "method": "POST",
                    "function": "process",
                    "line": 15,
                },
                {"path": "/status", "method": "GET", "function": "status", "line": 20},
            ],
            source_file="main.py",
            source_router="api_router",
            compute_type="cpu",
            resource_class="CpuLiveServerless",
        )

        config = generate_endpoint_config(handler, "data-processor")

        assert config["handler_id"] == "cpu_handler_87654321"
        assert config["handler_type"] == "load_balancer"
        assert config["compute_type"] == "cpu"
        assert config["resource_class"] == "CpuLiveServerless"

        endpoint_config = config["endpoint_config"]
        assert endpoint_config["name"] == "data-processor-cpu_handler_87654321"
        assert endpoint_config["type"] == "LB"
        assert endpoint_config["instanceIds"] == ["cpu5g-2-8"]
        assert "gpus" not in endpoint_config

    def test_generate_environment_variables(self):
        """Test generation of environment variables for handler."""
        handler = HandlerMetadata(
            handler_id="test_handler",
            handler_type="queue",
            serverless_config={"serverless": {}},
            routes=[
                {"path": "/hello", "method": "POST", "function": "hello", "line": 10},
            ],
            source_file="main.py",
            source_router="app",
            compute_type="gpu",
        )

        config = generate_endpoint_config(handler, "my-app")
        env_vars = config["environment_vars"]

        assert env_vars["HANDLER_ID"] == "test_handler"
        assert env_vars["HANDLER_TYPE"] == "queue"
        assert env_vars["HANDLER_SOURCE_FILE"] == "main.py"
        assert env_vars["HANDLER_SOURCE_ROUTER"] == "app"

        # Routes should be JSON-encoded
        routes_data = json.loads(env_vars["HANDLER_ROUTES"])
        assert len(routes_data) == 1
        assert routes_data[0]["path"] == "/hello"
        assert routes_data[0]["method"] == "POST"

    def test_infer_resource_class_from_compute_type(self):
        """Test resource class inference when not explicitly set."""
        gpu_handler = HandlerMetadata(
            handler_id="gpu_handler",
            handler_type="queue",
            serverless_config={"serverless": {}},
            routes=[],
            source_file="main.py",
            compute_type="gpu",
            resource_class=None,  # No explicit resource class
        )

        gpu_config = generate_endpoint_config(gpu_handler, "app")
        assert gpu_config["resource_class"] == "LiveServerless"

        cpu_handler = HandlerMetadata(
            handler_id="cpu_handler",
            handler_type="queue",
            serverless_config={"serverless": {}},
            routes=[],
            source_file="main.py",
            compute_type="cpu",
            resource_class=None,  # No explicit resource class
        )

        cpu_config = generate_endpoint_config(cpu_handler, "app")
        assert cpu_config["resource_class"] == "CpuLiveServerless"


class TestDeploymentManifest:
    """Tests for deployment manifest generation."""

    def test_generate_deployment_manifest(self, tmp_path):
        """Test generating complete deployment manifest."""
        handlers = [
            HandlerMetadata(
                handler_id="handler1",
                handler_type="queue",
                serverless_config={
                    "compute_type": "gpu",
                    "serverless": {"workersMax": 3},
                },
                routes=[
                    {
                        "path": "/hello",
                        "method": "POST",
                        "function": "hello",
                        "line": 10,
                    }
                ],
                source_file="main.py",
                source_router="app",
                compute_type="gpu",
            ),
            HandlerMetadata(
                handler_id="handler2",
                handler_type="load_balancer",
                serverless_config={
                    "compute_type": "cpu",
                    "serverless": {"workersMax": 5},
                },
                routes=[
                    {
                        "path": "/process",
                        "method": "GET",
                        "function": "process",
                        "line": 20,
                    }
                ],
                source_file="workers.py",
                source_router="worker_router",
                compute_type="cpu",
            ),
        ]

        discovery_result = DiscoveryResult(
            handlers=handlers,
            warnings=["Test warning"],
            stats={
                "total_handlers": 2,
                "queue_handlers": 1,
                "load_balancer_handlers": 1,
                "total_routes": 2,
            },
        )

        build_dir = tmp_path / "build"
        build_dir.mkdir()

        manifest = generate_deployment_manifest(discovery_result, "test-app", build_dir)

        assert manifest["version"] == "1.0"
        assert manifest["app_name"] == "test-app"
        assert "build_timestamp" in manifest
        assert manifest["build_dir"] == str(build_dir)
        assert len(manifest["handlers"]) == 2
        assert manifest["discovery_warnings"] == ["Test warning"]
        assert manifest["stats"]["total_handlers"] == 2

    def test_write_and_read_deployment_manifest(self, tmp_path):
        """Test writing and reading deployment manifest."""
        manifest = {
            "version": "1.0",
            "app_name": "test-app",
            "build_timestamp": "2025-11-14T10:00:00Z",
            "handlers": [
                {
                    "handler_id": "test_handler",
                    "handler_type": "queue",
                    "compute_type": "gpu",
                    "endpoint_config": {"name": "test-endpoint"},
                    "environment_vars": {"HANDLER_ID": "test_handler"},
                }
            ],
            "stats": {},
        }

        build_dir = tmp_path / "build"
        build_dir.mkdir()

        # Write manifest
        manifest_path = write_deployment_manifest(manifest, build_dir)
        assert manifest_path.exists()
        assert manifest_path.name == ".flash_deployment_manifest.json"

        # Read manifest back
        loaded_manifest = read_deployment_manifest(manifest_path)
        assert loaded_manifest["version"] == manifest["version"]
        assert loaded_manifest["app_name"] == manifest["app_name"]
        assert len(loaded_manifest["handlers"]) == 1
        assert loaded_manifest["handlers"][0]["handler_id"] == "test_handler"

    def test_manifest_includes_all_handler_fields(self, tmp_path):
        """Test that manifest includes all necessary handler fields."""
        handler = HandlerMetadata(
            handler_id="complete_handler",
            handler_type="queue",
            serverless_config={
                "compute_type": "gpu",
                "resource_class": "LiveServerless",
                "serverless": {"workersMax": 3},
            },
            routes=[
                {"path": "/test", "method": "POST", "function": "test_fn", "line": 5}
            ],
            source_file="app.py",
            source_router="main_router",
            compute_type="gpu",
            resource_class="LiveServerless",
        )

        discovery_result = DiscoveryResult(
            handlers=[handler],
            warnings=[],
            stats={"total_handlers": 1},
        )

        build_dir = tmp_path / "build"
        build_dir.mkdir()

        manifest = generate_deployment_manifest(discovery_result, "app", build_dir)
        handler_config = manifest["handlers"][0]

        # Verify all expected fields are present
        assert "handler_id" in handler_config
        assert "handler_type" in handler_config
        assert "compute_type" in handler_config
        assert "resource_class" in handler_config
        assert "endpoint_config" in handler_config
        assert "environment_vars" in handler_config
        assert "routes" in handler_config
        assert "source_file" in handler_config
        assert "source_router" in handler_config
