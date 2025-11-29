"""Unit tests for handler discovery and classification."""

import json

import pytest

from tetra_rp.cli.utils.ast_parser import (
    FastAPIASTParser,
    RemoteDecoratorParser,
    RouteInfo,
)
from tetra_rp.cli.utils.handler_discovery import (
    HandlerClassifier,
    HandlerDiscovery,
    HandlerMetadata,
    write_handler_metadata,
)


class TestFastAPIASTParser:
    """Tests for FastAPI AST parser."""

    def test_parse_simple_fastapi_app(self):
        """Test parsing a simple FastAPI application."""
        source = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process")
def process():
    return {"result": "processed"}
"""
        parser = FastAPIASTParser(source)
        app_info, routers = parser.parse()

        assert app_info is not None
        assert app_info.variable_name == "app"
        assert len(app_info.routes) == 2

        # Check GET route
        get_route = next(r for r in app_info.routes if r.method == "GET")
        assert get_route.path == "/health"
        assert get_route.function_name == "health"

        # Check POST route
        post_route = next(r for r in app_info.routes if r.method == "POST")
        assert post_route.path == "/process"
        assert post_route.function_name == "process"

    def test_parse_api_router(self):
        """Test parsing APIRouter instances."""
        source = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
def list_items():
    return []

@router.post("/items")
def create_item():
    return {}
"""
        parser = FastAPIASTParser(source)
        app_info, routers = parser.parse()

        assert app_info is None
        assert len(routers) == 1
        assert "router" in routers

        router = routers["router"]
        assert router.variable_name == "router"
        assert len(router.routes) == 2

    def test_parse_included_routers(self):
        """Test parsing app.include_router() calls."""
        source = """
from fastapi import FastAPI, APIRouter

app = FastAPI()
user_router = APIRouter()
admin_router = APIRouter()

app.include_router(user_router)
app.include_router(admin_router)
"""
        parser = FastAPIASTParser(source)
        app_info, routers = parser.parse()

        assert app_info is not None
        assert len(app_info.included_routers) == 2
        assert "user_router" in app_info.included_routers
        assert "admin_router" in app_info.included_routers

    def test_parse_multiple_http_methods(self):
        """Test parsing various HTTP methods."""
        source = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/items")
def get_items():
    pass

@app.post("/items")
def create_item():
    pass

@app.put("/items/{id}")
def update_item():
    pass

@app.delete("/items/{id}")
def delete_item():
    pass

@app.patch("/items/{id}")
def patch_item():
    pass
"""
        parser = FastAPIASTParser(source)
        app_info, routers = parser.parse()

        assert len(app_info.routes) == 5
        methods = {r.method for r in app_info.routes}
        assert methods == {"GET", "POST", "PUT", "DELETE", "PATCH"}


class TestRemoteDecoratorParser:
    """Tests for @remote decorator parser."""

    def test_parse_remote_with_live_serverless(self):
        """Test parsing @remote decorator with LiveServerless config."""
        source = """
from tetra_rp import remote, LiveServerless

config = LiveServerless(
    name="example_worker",
    workersMin=0,
    workersMax=3,
    idleTimeout=5,
)

@remote(config)
class ExampleWorker:
    def process(self, data):
        return data
"""
        parser = RemoteDecoratorParser(source)
        configs = parser.extract_remote_configs()

        assert "ExampleWorker" in configs
        worker_config = configs["ExampleWorker"]
        assert "serverless" in worker_config

        serverless = worker_config["serverless"]
        assert serverless["name"] == "example_worker"
        assert serverless["workersMin"] == 0
        assert serverless["workersMax"] == 3
        assert serverless["idleTimeout"] == 5

    def test_parse_remote_with_serverless_type_enum(self):
        """Test parsing @remote decorator with ServerlessType enum."""
        source = """
from tetra_rp import remote, LiveServerless, ServerlessType

config = LiveServerless(
    name="queue_worker",
    type=ServerlessType.QB,
    workersMin=0,
    workersMax=5,
)

@remote(config)
class QueueWorker:
    def process(self, data):
        return data
"""
        parser = RemoteDecoratorParser(source)
        configs = parser.extract_remote_configs()

        assert "QueueWorker" in configs
        worker_config = configs["QueueWorker"]
        assert "serverless" in worker_config

        serverless = worker_config["serverless"]
        assert serverless["name"] == "queue_worker"
        assert serverless["type"] == "QB"  # Enum value extracted
        assert serverless["workersMin"] == 0
        assert serverless["workersMax"] == 5

    def test_parse_remote_without_config(self):
        """Test parsing @remote decorator without arguments."""
        source = """
from tetra_rp import remote

@remote
class SimpleWorker:
    pass
"""
        parser = RemoteDecoratorParser(source)
        configs = parser.extract_remote_configs()

        assert "SimpleWorker" in configs
        assert configs["SimpleWorker"] == {}

    def test_parse_multiple_workers(self):
        """Test parsing multiple @remote decorated classes."""
        source = """
from tetra_rp import remote, LiveServerless

@remote(LiveServerless(name="worker1"))
class Worker1:
    pass

@remote(LiveServerless(name="worker2"))
class Worker2:
    pass
"""
        parser = RemoteDecoratorParser(source)
        configs = parser.extract_remote_configs()

        assert len(configs) == 2
        assert "Worker1" in configs
        assert "Worker2" in configs


class TestHandlerClassifier:
    """Tests for handler classification logic."""

    def test_classify_single_post_as_queue(self):
        """Single POST route should be queue-based."""
        routes = [
            RouteInfo(
                path="/process", method="POST", function_name="process", line_number=10
            )
        ]

        handler_type = HandlerClassifier.classify(routes)
        assert handler_type == "queue"

    def test_classify_multiple_routes_as_load_balancer(self):
        """Multiple routes should be load-balancer based."""
        routes = [
            RouteInfo(
                path="/items", method="POST", function_name="create", line_number=10
            ),
            RouteInfo(
                path="/items", method="GET", function_name="list", line_number=15
            ),
        ]

        handler_type = HandlerClassifier.classify(routes)
        assert handler_type == "load_balancer"

    def test_classify_any_get_as_load_balancer(self):
        """Any GET route should be load-balancer based."""
        routes = [
            RouteInfo(path="/items", method="GET", function_name="list", line_number=10)
        ]

        handler_type = HandlerClassifier.classify(routes)
        assert handler_type == "load_balancer"

    def test_classify_mixed_methods_as_load_balancer(self):
        """Mixed methods beyond single POST should be load-balancer."""
        routes = [
            RouteInfo(
                path="/items", method="POST", function_name="create", line_number=10
            ),
            RouteInfo(
                path="/items/{id}", method="PUT", function_name="update", line_number=15
            ),
        ]

        handler_type = HandlerClassifier.classify(routes)
        assert handler_type == "load_balancer"

    def test_classify_single_put_as_load_balancer(self):
        """Single PUT route should be load-balancer based."""
        routes = [
            RouteInfo(
                path="/items/{id}", method="PUT", function_name="update", line_number=10
            )
        ]

        handler_type = HandlerClassifier.classify(routes)
        assert handler_type == "load_balancer"

    def test_classify_with_explicit_type_lb(self):
        """Explicit type=LB should override route-based classification."""
        routes = [
            RouteInfo(
                path="/process", method="POST", function_name="process", line_number=10
            )
        ]
        config = {"serverless": {"type": "LB"}}

        handler_type = HandlerClassifier.classify(routes, config)
        assert handler_type == "load_balancer"

    def test_classify_with_explicit_type_qb(self):
        """Explicit type=QB should classify as queue."""
        routes = [
            RouteInfo(
                path="/process", method="POST", function_name="process", line_number=10
            )
        ]
        config = {"serverless": {"type": "QB"}}

        handler_type = HandlerClassifier.classify(routes, config)
        assert handler_type == "queue"

    def test_classify_multiple_routes_with_type_lb(self):
        """Multiple routes with type=LB should be load-balancer."""
        routes = [
            RouteInfo(
                path="/items", method="POST", function_name="create", line_number=10
            ),
            RouteInfo(
                path="/items", method="GET", function_name="list", line_number=15
            ),
        ]
        config = {"serverless": {"type": "LB"}}

        handler_type = HandlerClassifier.classify(routes, config)
        assert handler_type == "load_balancer"

    def test_classify_without_explicit_type_uses_routes(self):
        """Without explicit type, should use route-based classification."""
        routes = [
            RouteInfo(
                path="/process", method="POST", function_name="process", line_number=10
            )
        ]
        config = {"serverless": {}}  # No type specified

        handler_type = HandlerClassifier.classify(routes, config)
        assert handler_type == "queue"  # Route-based: single POST


class TestHandlerDiscovery:
    """Tests for handler discovery."""

    @pytest.fixture
    def temp_build_dir(self, tmp_path):
        """Create temporary build directory with sample files."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        # Create main.py with FastAPI app
        main_py = build_dir / "main.py"
        main_py.write_text(
            """
from fastapi import FastAPI, APIRouter

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process")
def process():
    return {}

# Router with single POST (queue-based)
queue_router = APIRouter()

@queue_router.post("/inference")
def run_inference():
    return {}

# Router with multiple routes (load-balancer)
api_router = APIRouter()

@api_router.get("/items")
def list_items():
    return []

@api_router.post("/items")
def create_item():
    return {}

app.include_router(queue_router)
app.include_router(api_router)
"""
        )

        # Create workers directory
        workers_dir = build_dir / "workers"
        workers_dir.mkdir()
        (workers_dir / "__init__.py").write_text("")

        return build_dir

    def test_discover_handlers_from_main_app(self, temp_build_dir):
        """Test discovering handlers from main FastAPI app."""
        discovery = HandlerDiscovery(temp_build_dir)
        result = discovery.discover()

        assert len(result.handlers) > 0
        assert result.stats["total_handlers"] > 0

        # Check that main app routes were discovered
        main_handlers = [h for h in result.handlers if "main_app" in h.handler_id]
        assert len(main_handlers) > 0

    def test_discover_queue_and_load_balancer_handlers(self, temp_build_dir):
        """Test that both queue and load-balancer handlers are discovered."""
        discovery = HandlerDiscovery(temp_build_dir)
        result = discovery.discover()

        queue_handlers = [h for h in result.handlers if h.handler_type == "queue"]
        lb_handlers = [h for h in result.handlers if h.handler_type == "load_balancer"]

        # Should have at least one of each type
        assert len(queue_handlers) > 0
        assert len(lb_handlers) > 0

    def test_discovery_generates_statistics(self, temp_build_dir):
        """Test that discovery generates correct statistics."""
        discovery = HandlerDiscovery(temp_build_dir)
        result = discovery.discover()

        stats = result.stats
        assert "total_handlers" in stats
        assert "queue_handlers" in stats
        assert "load_balancer_handlers" in stats
        assert "total_routes" in stats

        # Verify stats add up
        assert (
            stats["total_handlers"]
            == stats["queue_handlers"] + stats["load_balancer_handlers"]
        )

    def test_write_and_read_metadata(self, temp_build_dir):
        """Test writing and reading handler metadata."""
        discovery = HandlerDiscovery(temp_build_dir)
        result = discovery.discover()

        # Write metadata
        metadata_path = write_handler_metadata(temp_build_dir, result)
        assert metadata_path.exists()

        # Verify JSON structure
        metadata = json.loads(metadata_path.read_text())
        assert "handlers" in metadata
        assert "warnings" in metadata
        assert "stats" in metadata

        # Verify handlers have required fields
        for handler in metadata["handlers"]:
            assert "handler_id" in handler
            assert "handler_type" in handler
            assert "routes" in handler
            assert handler["handler_type"] in ("queue", "load_balancer")

    def test_discovery_without_main_py(self, tmp_path):
        """Test discovery when main.py doesn't exist."""
        build_dir = tmp_path / "empty"
        build_dir.mkdir()

        discovery = HandlerDiscovery(build_dir)
        result = discovery.discover()

        assert len(result.warnings) > 0
        assert any("main.py not found" in w for w in result.warnings)

    def test_discovery_with_no_routes(self, tmp_path):
        """Test discovery when FastAPI app has no routes."""
        build_dir = tmp_path / "no_routes"
        build_dir.mkdir()

        main_py = build_dir / "main.py"
        main_py.write_text(
            """
from fastapi import FastAPI

app = FastAPI()
"""
        )

        discovery = HandlerDiscovery(build_dir)
        result = discovery.discover()

        assert len(result.warnings) > 0
        assert any("no routes" in w.lower() for w in result.warnings)

    def test_discovery_parse_serverless_type_enum(self, tmp_path):
        """Test that ServerlessType enums are correctly parsed from worker configs."""
        build_dir = tmp_path / "enum_parsing"
        build_dir.mkdir()

        main_py = build_dir / "main.py"
        main_py.write_text(
            """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {}
"""
        )

        # Create worker with ServerlessType.LB enum
        workers_dir = build_dir / "workers"
        workers_dir.mkdir()

        worker_py = workers_dir / "test_worker.py"
        worker_py.write_text(
            """
from tetra_rp import remote, LiveServerless, ServerlessType

config = LiveServerless(
    name="test_worker",
    type=ServerlessType.LB,  # Enum should be parsed as "LB"
)

@remote(config)
class TestWorker:
    def process(self, data):
        return data
"""
        )

        discovery = HandlerDiscovery(build_dir)

        # Worker configs should have parsed the enum value
        worker_configs = discovery._parse_worker_configs()
        assert "TestWorker" in worker_configs
        assert worker_configs["TestWorker"]["serverless"]["type"] == "LB"

    def test_discovery_with_malformed_worker_file(self, tmp_path):
        """Test that malformed worker files don't crash discovery."""
        build_dir = tmp_path / "malformed_worker"
        build_dir.mkdir()

        # Valid main.py
        main_py = build_dir / "main.py"
        main_py.write_text(
            """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {}
"""
        )

        # Create workers directory with malformed file
        workers_dir = build_dir / "workers"
        workers_dir.mkdir()

        malformed_worker = workers_dir / "broken.py"
        malformed_worker.write_text(
            """
# Syntax error - missing closing parenthesis
from tetra_rp import LiveServerless

config = LiveServerless(
    name="broken"
    # Missing closing paren
"""
        )

        discovery = HandlerDiscovery(build_dir)
        result = discovery.discover()

        # Should have warning about failed parsing
        assert len(result.warnings) > 0
        assert any("Failed to parse" in w and "broken.py" in w for w in result.warnings)

        # Should still discover main app handler
        assert len(result.handlers) >= 1


class TestHandlerValidation:
    """Tests for handler validation."""

    def test_validate_handler_with_valid_type(self):
        """Test validation passes for valid ServerlessType values."""
        from tetra_rp.cli.utils.flash_app_integration import (
            validate_handler_for_deployment,
        )

        handler = HandlerMetadata(
            handler_id="test_handler",
            handler_type="queue",
            serverless_config={"serverless": {"type": "QB"}},
            routes=[{"path": "/process", "method": "POST", "function": "process"}],
            source_file="main.py",
        )

        is_valid, errors = validate_handler_for_deployment(handler)
        assert is_valid
        assert len(errors) == 0

    def test_validate_handler_with_invalid_type(self):
        """Test validation fails for invalid type values."""
        from tetra_rp.cli.utils.flash_app_integration import (
            validate_handler_for_deployment,
        )

        handler = HandlerMetadata(
            handler_id="test_handler",
            handler_type="queue",
            serverless_config={"serverless": {"type": "INVALID"}},
            routes=[{"path": "/process", "method": "POST", "function": "process"}],
            source_file="main.py",
        )

        is_valid, errors = validate_handler_for_deployment(handler)
        assert not is_valid
        assert len(errors) == 1
        assert "Invalid type" in errors[0]

    def test_validate_handler_with_lb_type(self):
        """Test validation passes for LB type."""
        from tetra_rp.cli.utils.flash_app_integration import (
            validate_handler_for_deployment,
        )

        handler = HandlerMetadata(
            handler_id="test_handler",
            handler_type="load_balancer",
            serverless_config={"serverless": {"type": "LB"}},
            routes=[
                {"path": "/users", "method": "GET", "function": "list_users"},
                {"path": "/users", "method": "POST", "function": "create_user"},
            ],
            source_file="main.py",
        )

        is_valid, errors = validate_handler_for_deployment(handler)
        assert is_valid
        assert len(errors) == 0
