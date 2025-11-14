"""Handler discovery and classification for Flash applications."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tetra_rp.cli.utils.ast_parser import (
    FastAPIAppInfo,
    RouteInfo,
    RouterInfo,
    parse_fastapi_file,
    parse_remote_configs,
)


@dataclass
class HandlerMetadata:
    """Metadata for a discovered handler."""

    handler_id: str
    handler_type: str  # "queue" or "load_balancer"
    serverless_config: dict[str, Any]
    routes: list[dict[str, Any]]
    source_file: str
    source_router: str | None = None


@dataclass
class DiscoveryResult:
    """Result of handler discovery process."""

    handlers: list[HandlerMetadata]
    warnings: list[str]
    stats: dict[str, int]


class HandlerClassifier:
    """Classifier for determining handler type based on routes."""

    @staticmethod
    def classify(
        routes: list[RouteInfo], serverless_config: dict[str, Any] | None = None
    ) -> str:
        """Classify handler as queue-based or load-balancer based.

        Classification priority:
        1. Explicit type in serverless config (user override)
        2. Route-based classification (default behavior)

        Route-based rules:
        - Single POST route only → queue
        - Any GET routes → load_balancer
        - Multiple routes (regardless of method) → load_balancer

        Args:
            routes: List of route information
            serverless_config: Optional serverless configuration dict

        Returns:
            "queue" or "load_balancer"
        """
        # Priority 1: Explicit type override in config
        if serverless_config:
            config_type = serverless_config.get("serverless", {}).get("type")
            if config_type == "LB":
                return "load_balancer"
            if config_type == "QB":
                return "queue"

        # Priority 2: Route-based classification
        if len(routes) == 1 and routes[0].method == "POST":
            return "queue"

        if any(route.method == "GET" for route in routes):
            return "load_balancer"

        return "load_balancer"


class HandlerDiscovery:
    """Discovers and classifies handlers from Flash application code."""

    def __init__(self, build_dir: Path):
        """Initialize handler discovery.

        Args:
            build_dir: Path to build directory containing application code
        """
        self.build_dir = build_dir
        self.warnings: list[str] = []
        self.handlers: list[HandlerMetadata] = []

    def discover(self) -> DiscoveryResult:
        """Discover all handlers in the application.

        Returns:
            DiscoveryResult with handlers, warnings, and statistics
        """
        self.warnings = []
        self.handlers = []

        # Parse main.py
        main_py = self.build_dir / "main.py"
        if not main_py.exists():
            self.warnings.append("main.py not found in build directory")
            return self._create_result()

        app_info, main_routers = parse_fastapi_file(main_py)

        # Parse worker configs
        worker_configs = self._parse_worker_configs()

        # Parse worker files for APIRouters
        worker_routers = self._parse_worker_routers()

        # Combine all routers
        all_routers = {**main_routers, **worker_routers}

        # Process main FastAPI app
        if app_info:
            self._process_fastapi_app(app_info, worker_configs)

        # Process APIRouters (from main.py and workers/)
        for router_var, router_info in all_routers.items():
            self._process_api_router(router_info, worker_configs)

        # Validate handlers
        self._validate_handlers()

        return self._create_result()

    def _parse_worker_configs(self) -> dict[str, dict[str, Any]]:
        """Parse all worker @remote configurations.

        Returns:
            Dict mapping worker class names to their configs
        """
        workers_dir = self.build_dir / "workers"
        if not workers_dir.exists():
            return {}

        all_configs: dict[str, dict[str, Any]] = {}

        for worker_file in workers_dir.glob("**/*.py"):
            # Skip private modules but allow __init__.py
            if worker_file.name.startswith("_") and worker_file.name != "__init__.py":
                continue

            try:
                configs = parse_remote_configs(worker_file)
                all_configs.update(configs)
            except Exception as e:
                self.warnings.append(f"Failed to parse {worker_file.name}: {e}")

        return all_configs

    def _parse_worker_routers(self) -> dict[str, RouterInfo]:
        """Parse APIRouters from worker files.

        Returns:
            Dict mapping router variable names to RouterInfo
        """
        workers_dir = self.build_dir / "workers"
        if not workers_dir.exists():
            return {}

        all_routers: dict[str, RouterInfo] = {}

        for worker_file in workers_dir.glob("**/*.py"):
            # Skip private modules but allow __init__.py
            if worker_file.name.startswith("_") and worker_file.name != "__init__.py":
                continue

            try:
                _, routers = parse_fastapi_file(worker_file)
                all_routers.update(routers)
            except Exception as e:
                self.warnings.append(
                    f"Failed to parse routers from {worker_file.name}: {e}"
                )

        return all_routers

    def _process_fastapi_app(
        self, app_info: FastAPIAppInfo, worker_configs: dict[str, dict[str, Any]]
    ) -> None:
        """Process main FastAPI app and create handlers.

        Args:
            app_info: FastAPI application information
            worker_configs: Worker serverless configurations
        """
        if not app_info.routes:
            self.warnings.append("Main FastAPI app has no routes defined")
            return

        # Group routes by serverless config
        route_groups = self._group_routes_by_config(app_info.routes, worker_configs)

        for config_hash, (routes, config) in route_groups.items():
            handler_id = f"main_app_{config_hash[:8]}"

            # Validate type=QB requires single POST endpoint
            config_type = config.get("serverless", {}).get("type")
            if config_type == "QB":
                if len(routes) != 1 or routes[0].method != "POST":
                    self.warnings.append(
                        f"Handler '{handler_id}' has type=QB but doesn't have a single POST endpoint. "
                        f"Queue-based handlers require exactly one POST route."
                    )

            handler_type = HandlerClassifier.classify(routes, config)

            self.handlers.append(
                HandlerMetadata(
                    handler_id=handler_id,
                    handler_type=handler_type,
                    serverless_config=config,
                    routes=[self._route_to_dict(route) for route in routes],
                    source_file="main.py",
                    source_router=app_info.variable_name,
                )
            )

    def _process_api_router(
        self, router_info: RouterInfo, worker_configs: dict[str, dict[str, Any]]
    ) -> None:
        """Process APIRouter and create handlers.

        Each APIRouter becomes its own handler, regardless of config grouping.
        Routes within the same router share the same serverless configuration.

        Args:
            router_info: APIRouter information
            worker_configs: Worker serverless configurations
        """
        if not router_info.routes:
            self.warnings.append(
                f"Router '{router_info.variable_name}' has no routes defined"
            )
            return

        # Infer config for this router (use first route as representative)
        config = self._infer_route_config(router_info.routes[0], worker_configs)
        config_hash = self._hash_config(config)

        handler_id = f"{router_info.variable_name}_{config_hash[:8]}"

        # Validate type=QB requires single POST endpoint
        config_type = config.get("serverless", {}).get("type")
        if config_type == "QB":
            if len(router_info.routes) != 1 or router_info.routes[0].method != "POST":
                self.warnings.append(
                    f"Router '{router_info.variable_name}' has type=QB but doesn't have a single POST endpoint. "
                    f"Queue-based handlers require exactly one POST route."
                )

        handler_type = HandlerClassifier.classify(router_info.routes, config)

        self.handlers.append(
            HandlerMetadata(
                handler_id=handler_id,
                handler_type=handler_type,
                serverless_config=config,
                routes=[self._route_to_dict(route) for route in router_info.routes],
                source_file="main.py",
                source_router=router_info.variable_name,
            )
        )

    def _group_routes_by_config(
        self, routes: list[RouteInfo], worker_configs: dict[str, dict[str, Any]]
    ) -> dict[str, tuple[list[RouteInfo], dict[str, Any]]]:
        """Group routes by their serverless configuration.

        Routes with the same config hash are grouped into a single handler.

        Args:
            routes: List of routes to group
            worker_configs: Worker serverless configurations

        Returns:
            Dict mapping config hash to (routes, config) tuple
        """
        groups: dict[str, tuple[list[RouteInfo], dict[str, Any]]] = {}

        for route in routes:
            # For now, use empty config (future: infer from function body analysis)
            config = self._infer_route_config(route, worker_configs)
            config_hash = self._hash_config(config)

            if config_hash not in groups:
                groups[config_hash] = ([], config)

            groups[config_hash][0].append(route)

        return groups

    def _infer_route_config(
        self, route: RouteInfo, worker_configs: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Infer serverless config for a route.

        This is a simplified implementation. Future enhancement would analyze
        the function body to detect which worker class is instantiated.

        Args:
            route: Route information
            worker_configs: Available worker configurations

        Returns:
            Serverless configuration dict
        """
        default_config: dict[str, Any] = {"serverless": {}}

        # TODO: Analyze function body to detect worker instantiation
        # For now, return default config
        return default_config

    def _hash_config(self, config: dict[str, Any]) -> str:
        """Create hash of serverless configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Hex digest hash string
        """
        config_json = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()

    def _route_to_dict(self, route: RouteInfo) -> dict[str, Any]:
        """Convert RouteInfo to dictionary.

        Args:
            route: Route information

        Returns:
            Dictionary representation
        """
        return {
            "path": route.path,
            "method": route.method,
            "function": route.function_name,
            "line": route.line_number,
        }

    def _validate_handlers(self) -> None:
        """Validate discovered handlers and add warnings."""
        if not self.handlers:
            self.warnings.append("No handlers discovered in application")
            return

        # Check for duplicate handler IDs
        handler_ids = [h.handler_id for h in self.handlers]
        duplicates = set([id for id in handler_ids if handler_ids.count(id) > 1])
        if duplicates:
            self.warnings.append(f"Duplicate handler IDs found: {duplicates}")

        # Check for conflicting routes across handlers
        all_routes: dict[tuple[str, str], str] = {}
        for handler in self.handlers:
            for route in handler.routes:
                key = (route["method"], route["path"])
                if key in all_routes:
                    self.warnings.append(
                        f"Route conflict: {route['method']} {route['path']} "
                        f"defined in both {all_routes[key]} and {handler.handler_id}"
                    )
                else:
                    all_routes[key] = handler.handler_id

    def _create_result(self) -> DiscoveryResult:
        """Create discovery result with statistics.

        Returns:
            DiscoveryResult object
        """
        queue_count = sum(1 for h in self.handlers if h.handler_type == "queue")
        lb_count = sum(1 for h in self.handlers if h.handler_type == "load_balancer")

        stats = {
            "total_handlers": len(self.handlers),
            "queue_handlers": queue_count,
            "load_balancer_handlers": lb_count,
            "total_routes": sum(len(h.routes) for h in self.handlers),
        }

        return DiscoveryResult(
            handlers=self.handlers, warnings=self.warnings, stats=stats
        )


def discover_and_classify_handlers(build_dir: Path) -> DiscoveryResult:
    """Discover and classify handlers in a Flash application.

    Args:
        build_dir: Path to build directory

    Returns:
        DiscoveryResult with handlers and metadata
    """
    discovery = HandlerDiscovery(build_dir)
    return discovery.discover()


def write_handler_metadata(build_dir: Path, result: DiscoveryResult) -> Path:
    """Write handler metadata to JSON file in build directory.

    Args:
        build_dir: Path to build directory
        result: Discovery result to serialize

    Returns:
        Path to created metadata file
    """
    metadata_path = build_dir / ".flash_handlers.json"

    metadata = {
        "handlers": [asdict(handler) for handler in result.handlers],
        "warnings": result.warnings,
        "stats": result.stats,
    }

    metadata_path.write_text(json.dumps(metadata, indent=2))
    return metadata_path


def read_handler_metadata(metadata_path: Path) -> DiscoveryResult:
    """Read handler metadata from JSON file.

    Args:
        metadata_path: Path to .flash_handlers.json file

    Returns:
        DiscoveryResult reconstructed from file
    """
    data = json.loads(metadata_path.read_text())

    handlers = [HandlerMetadata(**handler) for handler in data["handlers"]]

    return DiscoveryResult(
        handlers=handlers,
        warnings=data.get("warnings", []),
        stats=data.get("stats", {}),
    )
