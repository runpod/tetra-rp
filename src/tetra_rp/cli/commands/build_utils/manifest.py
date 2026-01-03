"""Builder for flash_manifest.json."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .scanner import RemoteFunctionMetadata


@dataclass
class ManifestFunction:
    """Function entry in manifest."""

    name: str
    module: str
    is_async: bool
    is_class: bool


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

        for resource_name, functions in sorted(resources.items()):
            handler_file = f"handler_{resource_name}.py"

            functions_list = [
                {
                    "name": f.function_name,
                    "module": f.module_path,
                    "is_async": f.is_async,
                    "is_class": f.is_class,
                }
                for f in functions
            ]

            resources_dict[resource_name] = {
                "resource_type": "LiveServerless",
                "handler_file": handler_file,
                "functions": functions_list,
            }

            # Build function registry for quick lookup
            for f in functions:
                function_registry[f.function_name] = resource_name

        return {
            "version": "1.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_name": self.project_name,
            "resources": resources_dict,
            "function_registry": function_registry,
        }

    def write_to_file(self, output_path: Path) -> Path:
        """Write manifest to file."""
        manifest = self.build()
        output_path.write_text(json.dumps(manifest, indent=2))
        return output_path
