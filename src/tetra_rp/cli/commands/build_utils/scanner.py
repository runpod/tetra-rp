"""AST scanner for discovering @remote decorated functions and classes."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RemoteFunctionMetadata:
    """Metadata about a @remote decorated function or class."""

    function_name: str
    module_path: str
    resource_config_name: str
    is_async: bool
    is_class: bool
    file_path: Path


class RemoteDecoratorScanner:
    """Scans Python files for @remote decorators and extracts metadata."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.py_files: List[Path] = []
        self.resource_configs: Dict[str, str] = {}

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
            except Exception:
                # Skip files that fail to parse
                pass

        # Second pass: extract @remote decorated functions
        for py_file in self.py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                functions.extend(self._extract_remote_functions(tree, py_file))
            except Exception:
                # Skip files that fail to parse
                pass

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
                            # Store mapping of variable name to resource config
                            key = f"{module_path}:{config_name}"
                            self.resource_configs[key] = config_name

                            # Also store just the name for local lookups
                            self.resource_configs[config_name] = config_name

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

                        metadata = RemoteFunctionMetadata(
                            function_name=node.name,
                            module_path=module_path,
                            resource_config_name=resource_config_name,
                            is_async=is_async,
                            is_class=is_class,
                            file_path=py_file,
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
