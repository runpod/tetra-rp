"""Builder for flash_manifest.json."""

import importlib.util
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scanner import RemoteFunctionMetadata

logger = logging.getLogger(__name__)

RESERVED_PATHS = ["/execute", "/ping", "/manifest"]


@dataclass
class ManifestFunction:
    """Function entry in manifest."""

    name: str
    module: str
    is_async: bool
    is_class: bool
    http_method: Optional[str] = None  # HTTP method for LB endpoints (GET, POST, etc.)
    http_path: Optional[str] = None  # HTTP path for LB endpoints (/api/process)
    is_load_balanced: bool = False  # Determined by isinstance() at scan time
    is_live_resource: bool = False  # LiveLoadBalancer vs LoadBalancerSlsResource
    config_variable: Optional[str] = None  # Variable name like "gpu_config"


@dataclass
class ManifestResource:
    """Resource config entry in manifest."""

    resource_type: str
    handler_file: str
    functions: List[ManifestFunction]
    is_load_balanced: bool = False  # Determined by isinstance() at scan time
    is_live_resource: bool = False  # LiveLoadBalancer vs LoadBalancerSlsResource
    config_variable: Optional[str] = None  # Variable name for test-mothership
    imageName: Optional[str] = None  # Docker image name for auto-provisioning
    templateId: Optional[str] = None  # RunPod template ID for auto-provisioning
    gpuIds: Optional[list] = None  # GPU types/IDs for auto-provisioning
    workersMin: Optional[int] = None  # Min worker count for auto-provisioning
    workersMax: Optional[int] = None  # Max worker count for auto-provisioning


class ManifestBuilder:
    """Builds flash_manifest.json from discovered remote functions."""

    def __init__(
        self,
        project_name: str,
        remote_functions: List[RemoteFunctionMetadata],
        scanner=None,
    ):
        self.project_name = project_name
        self.remote_functions = remote_functions
        self.scanner = (
            scanner  # Optional: RemoteDecoratorScanner with resource config info
        )

    def _extract_deployment_config(
        self, resource_name: str, config_variable: Optional[str], resource_type: str
    ) -> Dict[str, Any]:
        """Extract deployment config (imageName, templateId, etc.) from resource object.

        Args:
            resource_name: Name of the resource
            config_variable: Variable name of the resource config (e.g., "gpu_config")
            resource_type: Type of the resource (e.g., "LiveServerless")

        Returns:
            Dictionary with deployment config (may be empty if resource not found)
        """
        config = {}

        # If no scanner or config variable, can't extract deployment config
        if not self.scanner or not config_variable:
            return config

        try:
            # Get the module where this resource is defined
            # Try to find it in the scanner's discovered files
            resource_file = None
            for func in self.remote_functions:
                if func.config_variable == config_variable:
                    resource_file = func.file_path
                    break

            if not resource_file or not resource_file.exists():
                return config

            # Dynamically import the module and extract the resource config
            spec = importlib.util.spec_from_file_location(
                resource_file.stem, resource_file
            )
            if not spec or not spec.loader:
                return config

            module = importlib.util.module_from_spec(spec)
            # Add module to sys.modules temporarily to allow relative imports
            sys.modules[spec.name] = module

            try:
                spec.loader.exec_module(module)

                # Get the resource config object
                if hasattr(module, config_variable):
                    resource_config = getattr(module, config_variable)

                    # Extract deployment config properties
                    if (
                        hasattr(resource_config, "imageName")
                        and resource_config.imageName
                    ):
                        config["imageName"] = resource_config.imageName

                    if (
                        hasattr(resource_config, "templateId")
                        and resource_config.templateId
                    ):
                        config["templateId"] = resource_config.templateId

                    if hasattr(resource_config, "gpuIds") and resource_config.gpuIds:
                        config["gpuIds"] = resource_config.gpuIds

                    if hasattr(resource_config, "workersMin"):
                        config["workersMin"] = resource_config.workersMin

                    if hasattr(resource_config, "workersMax"):
                        config["workersMax"] = resource_config.workersMax

                    # Extract template configuration if present
                    if (
                        hasattr(resource_config, "template")
                        and resource_config.template
                    ):
                        template_obj = resource_config.template
                        template_config = {}

                        # Extract only the configurable template fields
                        if hasattr(template_obj, "containerDiskInGb"):
                            template_config["containerDiskInGb"] = (
                                template_obj.containerDiskInGb
                            )
                        if hasattr(template_obj, "dockerArgs"):
                            template_config["dockerArgs"] = template_obj.dockerArgs
                        if hasattr(template_obj, "startScript"):
                            template_config["startScript"] = template_obj.startScript
                        if hasattr(template_obj, "advancedStart"):
                            template_config["advancedStart"] = (
                                template_obj.advancedStart
                            )
                        if hasattr(template_obj, "containerRegistryAuthId"):
                            template_config["containerRegistryAuthId"] = (
                                template_obj.containerRegistryAuthId
                            )

                        if template_config:
                            config["template"] = template_config

            finally:
                # Clean up module from sys.modules to avoid conflicts
                if spec.name in sys.modules:
                    del sys.modules[spec.name]

        except Exception as e:
            # Log warning but don't fail - deployment config is optional
            logger.debug(
                f"Failed to extract deployment config for {resource_name}: {e}"
            )

        return config

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

            # Extract flags from first function (determined by isinstance() at scan time)
            is_load_balanced = functions[0].is_load_balanced if functions else False
            is_live_resource = functions[0].is_live_resource if functions else False

            # Validate and collect routing for LB endpoints
            resource_routes = {}
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
                    if f.http_path in RESERVED_PATHS:
                        raise ValueError(
                            f"Function '{f.function_name}' cannot use reserved path '{f.http_path}'. "
                            f"Reserved paths: {', '.join(RESERVED_PATHS)}"
                        )

            # Extract config_variable from first function (all functions in same resource share same config)
            config_variable = functions[0].config_variable if functions else None

            functions_list = [
                {
                    "name": f.function_name,
                    "module": f.module_path,
                    "is_async": f.is_async,
                    "is_class": f.is_class,
                    "is_load_balanced": f.is_load_balanced,
                    "is_live_resource": f.is_live_resource,
                    "config_variable": f.config_variable,
                    **(
                        {"http_method": f.http_method, "http_path": f.http_path}
                        if is_load_balanced
                        else {}
                    ),
                }
                for f in functions
            ]

            # Extract deployment config (imageName, templateId, etc.) for auto-provisioning
            deployment_config = self._extract_deployment_config(
                resource_name, config_variable, resource_type
            )

            resources_dict[resource_name] = {
                "resource_type": resource_type,
                "handler_file": handler_file,
                "functions": functions_list,
                "is_load_balanced": is_load_balanced,
                "is_live_resource": is_live_resource,
                "config_variable": config_variable,
                **deployment_config,  # Include imageName, templateId, gpuIds, workers config
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
