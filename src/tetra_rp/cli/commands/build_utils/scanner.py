"""AST scanner for discovering @remote decorated functions and classes."""

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RemoteFunctionMetadata:
    """Metadata about a @remote decorated function or class."""

    function_name: str
    module_path: str
    resource_config_name: str
    resource_type: str
    is_async: bool
    is_class: bool
    file_path: Path
    http_method: Optional[str] = None  # HTTP method for LB endpoints: GET, POST, etc.
    http_path: Optional[str] = None    # HTTP path for LB endpoints: /api/process


class RemoteDecoratorScanner:
    """Scans Python files for @remote decorators and extracts metadata."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.py_files: List[Path] = []
        self.resource_configs: Dict[str, str] = {}  # name -> name
        self.resource_types: Dict[str, str] = {}  # name -> type

    def discover_remote_functions(self) -> List[RemoteFunctionMetadata]:
        """Discover all @remote decorated functions and classes."""
        functions = []

        # Find all Python files
        self.py_files = list(self.project_dir.rglob("*.py"))

        # First pass: extract all resource configs from all files
        for py_file in self.py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                self._extract_resource_configs(tree, py_file)
            except UnicodeDecodeError:
                logger.debug(f"Skipping non-UTF-8 file: {py_file}")
            except SyntaxError as e:
                logger.warning(f"Syntax error in {py_file}: {e}")
            except Exception as e:
                logger.debug(f"Failed to parse {py_file}: {e}")

        # Second pass: extract @remote decorated functions
        for py_file in self.py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                functions.extend(self._extract_remote_functions(tree, py_file))
            except UnicodeDecodeError:
                logger.debug(f"Skipping non-UTF-8 file: {py_file}")
            except SyntaxError as e:
                logger.warning(f"Syntax error in {py_file}: {e}")
            except Exception as e:
                logger.debug(f"Failed to parse {py_file}: {e}")

        return functions

    def _extract_resource_configs(self, tree: ast.AST, py_file: Path) -> None:
        """Extract resource config variable assignments."""
        module_path = self._get_module_path(py_file)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Look for assignments like: gpu_config = LiveServerless(...)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        config_name = target.id
                        config_type = self._get_call_type(node.value)

                        if config_type and "Serverless" in config_type:
                            # Store mapping of variable name to name and type separately
                            key = f"{module_path}:{config_name}"
                            self.resource_configs[key] = config_name
                            self.resource_types[key] = config_type

                            # Also store just the name for local lookups
                            self.resource_configs[config_name] = config_name
                            self.resource_types[config_name] = config_type

    def _extract_remote_functions(
        self, tree: ast.AST, py_file: Path
    ) -> List[RemoteFunctionMetadata]:
        """Extract @remote decorated functions and classes."""
        module_path = self._get_module_path(py_file)
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Check if this node has @remote decorator
                remote_decorator = self._find_remote_decorator(node.decorator_list)

                if remote_decorator:
                    # Extract resource config name from decorator
                    resource_config_name = self._extract_resource_config_name(
                        remote_decorator, module_path
                    )

                    if resource_config_name:
                        is_async = isinstance(node, ast.AsyncFunctionDef)
                        is_class = isinstance(node, ast.ClassDef)

                        # Get resource type for this config
                        resource_type = self._get_resource_type(resource_config_name)

                        # Extract HTTP routing metadata (for LB endpoints)
                        http_method, http_path = self._extract_http_routing(remote_decorator)

                        metadata = RemoteFunctionMetadata(
                            function_name=node.name,
                            module_path=module_path,
                            resource_config_name=resource_config_name,
                            resource_type=resource_type,
                            is_async=is_async,
                            is_class=is_class,
                            file_path=py_file,
                            http_method=http_method,
                            http_path=http_path,
                        )
                        functions.append(metadata)

        return functions

    def _find_remote_decorator(self, decorators: List[ast.expr]) -> Optional[ast.expr]:
        """Find @remote decorator in a list of decorators."""
        for decorator in decorators:
            # Handle @remote or @remote(...)
            if isinstance(decorator, ast.Name):
                if decorator.id == "remote":
                    return decorator
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    if decorator.func.id == "remote":
                        return decorator
                elif isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == "remote":
                        return decorator

        return None

    def _extract_resource_config_name(
        self, decorator: ast.expr, module_path: str
    ) -> Optional[str]:
        """Extract resource_config name from @remote decorator."""
        if isinstance(decorator, ast.Name):
            # @remote without arguments
            return None

        if isinstance(decorator, ast.Call):
            # @remote(...) with arguments
            # Look for resource_config= or first positional arg
            for keyword in decorator.keywords:
                if keyword.arg == "resource_config":
                    return self._extract_name_from_expr(keyword.value, module_path)

            # Try first positional argument
            if decorator.args:
                return self._extract_name_from_expr(decorator.args[0], module_path)

        return None

    def _extract_name_from_expr(
        self, expr: ast.expr, module_path: str
    ) -> Optional[str]:
        """Extract config name from an expression (Name or Call)."""
        if isinstance(expr, ast.Name):
            # Variable reference: @remote(gpu_config)
            config_name = expr.id

            # Try to resolve from our resource configs map
            if config_name in self.resource_configs:
                return self.resource_configs[config_name]

            # Try module-scoped lookup
            full_key = f"{module_path}:{config_name}"
            if full_key in self.resource_configs:
                return self.resource_configs[full_key]

            # Fall back to the variable name itself
            return config_name

        elif isinstance(expr, ast.Call):
            # Direct instantiation: @remote(LiveServerless(name="gpu_config"))
            # Try to extract the name= argument
            for keyword in expr.keywords:
                if keyword.arg == "name":
                    if isinstance(keyword.value, ast.Constant):
                        return keyword.value.value

        return None

    def _get_call_type(self, expr: ast.expr) -> Optional[str]:
        """Get the type name of a call expression."""
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                return expr.func.id
            elif isinstance(expr.func, ast.Attribute):
                return expr.func.attr

        return None

    def _get_resource_type(self, resource_config_name: str) -> str:
        """Get the resource type for a given config name."""
        if resource_config_name in self.resource_types:
            return self.resource_types[resource_config_name]
        # Default to LiveServerless if type not found
        return "LiveServerless"

    def _sanitize_resource_name(self, name: str) -> str:
        """Sanitize resource config name for use in filenames.

        Replaces invalid filename characters with underscores and ensures
        the name starts with a letter or underscore (valid for Python identifiers).

        Args:
            name: Raw resource config name

        Returns:
            Sanitized name safe for use in filenames and as Python identifiers
        """
        # Replace invalid characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Ensure it starts with a letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == "_"):
            sanitized = f"_{sanitized}"

        return sanitized or "_"

    def _get_module_path(self, py_file: Path) -> str:
        """Convert file path to module path."""
        try:
            # Get relative path from project directory
            rel_path = py_file.relative_to(self.project_dir)

            # Remove .py extension and convert / to .
            module = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")

            return module
        except ValueError:
            # If relative_to fails, just use filename
            return py_file.stem

    def _extract_http_routing(
        self, decorator: ast.expr
    ) -> tuple[Optional[str], Optional[str]]:
        """Extract HTTP method and path from @remote decorator.

        Returns:
            Tuple of (method, path) or (None, None) if not found.
            method: GET, POST, PUT, DELETE, PATCH
            path: /api/endpoint routes
        """
        if not isinstance(decorator, ast.Call):
            return None, None

        http_method = None
        http_path = None

        # Extract keyword arguments: method="POST", path="/api/process"
        for keyword in decorator.keywords:
            if keyword.arg == "method":
                if isinstance(keyword.value, ast.Constant):
                    http_method = keyword.value.value
            elif keyword.arg == "path":
                if isinstance(keyword.value, ast.Constant):
                    http_path = keyword.value.value

        return http_method, http_path
