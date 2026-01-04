"""Builder for flash_manifest.json."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scanner import RemoteFunctionMetadata


@dataclass
class ManifestFunction:
    """Function entry in manifest."""

    name: str
    module: str
    is_async: bool
    is_class: bool
    http_method: Optional[str] = None  # HTTP method for LB endpoints (GET, POST, etc.)
    http_path: Optional[str] = None  # HTTP path for LB endpoints (/api/process)


@dataclass
class ManifestResource:
    """Resource config entry in manifest."""

    resource_type: str
    handler_file: str
    functions: List[ManifestFunction]


class ManifestBuilder:
    """Builds flash_manifest.json from discovered remote functions."""

    def __init__(
        self, project_name: str, remote_functions: List[RemoteFunctionMetadata]
    ):
        self.project_name = project_name
        self.remote_functions = remote_functions

    def build(self) -> Dict[str, Any]:
        """Build the manifest dictionary."""
        # Group functions by resource_config_name
        resources: Dict[str, List[RemoteFunctionMetadata]] = {}

        for func in self.remote_functions:
            if func.resource_config_name not in resources:
                resources[func.resource_config_name] = []
            resources[func.resource_config_name].append(func)

        # Build manifest structure
        resources_dict: Dict[str, Dict[str, Any]] = {}
        function_registry: Dict[str, str] = {}
        routes_dict: Dict[
            str, Dict[str, str]
        ] = {}  # resource_name -> {route_key -> function_name}

        for resource_name, functions in sorted(resources.items()):
            handler_file = f"handler_{resource_name}.py"

            # Use actual resource type from first function in group
            resource_type = (
                functions[0].resource_type if functions else "LiveServerless"
            )

            # Validate and collect routing for LB endpoints
            resource_routes = {}
            is_load_balanced = resource_type in [
                "LoadBalancerSlsResource",
                "LiveLoadBalancer",
            ]
            if is_load_balanced:
                for f in functions:
                    if not f.http_method or not f.http_path:
                        raise ValueError(
                            f"{resource_type} endpoint '{resource_name}' requires "
                            f"method and path for function '{f.function_name}'. "
                            f"Got method={f.http_method}, path={f.http_path}"
                        )

                    # Check for route conflicts (same method + path)
                    route_key = f"{f.http_method} {f.http_path}"
                    if route_key in resource_routes:
                        raise ValueError(
                            f"Duplicate route '{route_key}' in resource '{resource_name}': "
                            f"both '{resource_routes[route_key]}' and '{f.function_name}' "
                            f"are mapped to the same route"
                        )
                    resource_routes[route_key] = f.function_name

                    # Check for reserved paths
                    if f.http_path in ["/execute", "/ping"]:
                        raise ValueError(
                            f"Function '{f.function_name}' cannot use reserved path '{f.http_path}'. "
                            f"Reserved paths: /execute, /ping"
                        )

            functions_list = [
                {
                    "name": f.function_name,
                    "module": f.module_path,
                    "is_async": f.is_async,
                    "is_class": f.is_class,
                    **(
                        {"http_method": f.http_method, "http_path": f.http_path}
                        if is_load_balanced
                        else {}
                    ),
                }
                for f in functions
            ]

            resources_dict[resource_name] = {
                "resource_type": resource_type,
                "handler_file": handler_file,
                "functions": functions_list,
            }

            # Store routes for LB endpoints
            if resource_routes:
                routes_dict[resource_name] = resource_routes

            # Build function registry for quick lookup
            for f in functions:
                if f.function_name in function_registry:
                    raise ValueError(
                        f"Duplicate function name '{f.function_name}' found in "
                        f"resources '{function_registry[f.function_name]}' and '{resource_name}'"
                    )
                function_registry[f.function_name] = resource_name

        manifest = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "project_name": self.project_name,
            "resources": resources_dict,
            "function_registry": function_registry,
        }

        # Add routes section if there are LB endpoints with routing
        if routes_dict:
            manifest["routes"] = routes_dict

        return manifest

    def write_to_file(self, output_path: Path) -> Path:
        """Write manifest to file."""
        manifest = self.build()
        output_path.write_text(json.dumps(manifest, indent=2))
        return output_path
