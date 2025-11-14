"""AST parsing utilities for FastAPI application analysis."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RouteInfo:
    """Information about a FastAPI route."""

    path: str
    method: str
    function_name: str
    line_number: int


@dataclass
class RouterInfo:
    """Information about an APIRouter instance."""

    variable_name: str
    routes: list[RouteInfo]
    line_number: int


@dataclass
class FastAPIAppInfo:
    """Information about the main FastAPI application."""

    variable_name: str
    routes: list[RouteInfo]
    included_routers: list[str]
    line_number: int


class FastAPIASTParser:
    """Parser for FastAPI application source code using AST."""

    HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}

    def __init__(self, source_code: str):
        """Initialize parser with Python source code.

        Args:
            source_code: Python source code as string
        """
        self.source_code = source_code
        self.tree = ast.parse(source_code)
        self.fastapi_app: FastAPIAppInfo | None = None
        self.routers: dict[str, RouterInfo] = {}

    def parse(self) -> tuple[FastAPIAppInfo | None, dict[str, RouterInfo]]:
        """Parse the source code and extract FastAPI app and routers.

        Returns:
            Tuple of (FastAPIAppInfo, dict of RouterInfo by variable name)
        """
        self._find_fastapi_instances()
        self._extract_routes()
        return self.fastapi_app, self.routers

    def _find_fastapi_instances(self) -> None:
        """Find FastAPI() and APIRouter() instantiations."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                self._check_fastapi_assignment(node)

    def _check_fastapi_assignment(self, node: ast.Assign) -> None:
        """Check if assignment creates FastAPI or APIRouter instance."""
        if not isinstance(node.value, ast.Call):
            return

        call_name = self._get_call_name(node.value)
        if not call_name:
            return

        # Handle FastAPI instantiation
        if call_name in ("FastAPI", "API"):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                self.fastapi_app = FastAPIAppInfo(
                    variable_name=var_name,
                    routes=[],
                    included_routers=[],
                    line_number=node.lineno,
                )

        # Handle APIRouter instantiation
        elif call_name in ("APIRouter", "Router"):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                self.routers[var_name] = RouterInfo(
                    variable_name=var_name, routes=[], line_number=node.lineno
                )

    def _extract_routes(self) -> None:
        """Extract route definitions from decorators."""
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_route_from_function(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                self._extract_included_router(node.value)

    def _extract_route_from_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Extract route information from decorated function."""
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            route_info = self._parse_route_decorator(decorator, node.name, node.lineno)
            if route_info:
                router_var, route = route_info
                if (
                    router_var == self.fastapi_app.variable_name
                    if self.fastapi_app
                    else None
                ):
                    if self.fastapi_app:
                        self.fastapi_app.routes.append(route)
                elif router_var in self.routers:
                    self.routers[router_var].routes.append(route)

    def _parse_route_decorator(
        self, decorator: ast.Call, func_name: str, lineno: int
    ) -> tuple[str, RouteInfo] | None:
        """Parse a route decorator call.

        Args:
            decorator: AST Call node representing the decorator
            func_name: Name of the decorated function
            lineno: Line number of the function

        Returns:
            Tuple of (router_variable_name, RouteInfo) or None
        """
        if not isinstance(decorator.func, ast.Attribute):
            return None

        method = decorator.func.attr.lower()
        if method not in self.HTTP_METHODS:
            return None

        # Get router variable name (e.g., "app" in "app.get(...)")
        if not isinstance(decorator.func.value, ast.Name):
            return None
        router_var = decorator.func.value.id

        # Extract path from first positional argument
        if not decorator.args:
            return None

        path_node = decorator.args[0]
        if isinstance(path_node, ast.Constant):
            path = path_node.value
        elif isinstance(path_node, ast.Str):
            path = path_node.s
        else:
            return None

        route = RouteInfo(
            path=path,
            method=method.upper(),
            function_name=func_name,
            line_number=lineno,
        )

        return (router_var, route)

    def _extract_included_router(self, node: ast.Call) -> None:
        """Extract app.include_router() calls."""
        if not isinstance(node.func, ast.Attribute):
            return

        if node.func.attr != "include_router":
            return

        # Get the app variable (e.g., "app" in "app.include_router(...)")
        if not isinstance(node.func.value, ast.Name):
            return

        app_var = node.func.value.id
        if self.fastapi_app and app_var == self.fastapi_app.variable_name:
            # Extract router variable from first argument
            if node.args and isinstance(node.args[0], ast.Name):
                router_var = node.args[0].id
                self.fastapi_app.included_routers.append(router_var)

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name of the called function/class."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None


class RemoteDecoratorParser:
    """Parser for @remote decorator configurations."""

    def __init__(self, source_code: str):
        """Initialize parser with Python source code.

        Args:
            source_code: Python source code as string
        """
        self.source_code = source_code
        self.tree = ast.parse(source_code)
        self.config_variables: dict[str, dict[str, Any]] = {}

    def extract_remote_configs(self) -> dict[str, dict[str, Any]]:
        """Extract @remote decorator configurations mapped by class name.

        Returns:
            Dict mapping class names to their serverless configs
        """
        # First pass: extract config variable assignments
        self._extract_config_variables()

        # Second pass: extract @remote decorators
        configs: dict[str, dict[str, Any]] = {}

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                config = self._extract_remote_from_class(node)
                if config is not None:
                    configs[node.name] = config

        return configs

    def _extract_config_variables(self) -> None:
        """Extract LiveServerless config variable assignments."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    call_name = self._get_call_name(node.value)
                    if call_name in ("LiveServerless", "serverless"):
                        config = self._parse_live_serverless(node.value)
                        if config and len(node.targets) == 1:
                            if isinstance(node.targets[0], ast.Name):
                                var_name = node.targets[0].id
                                self.config_variables[var_name] = {"serverless": config}

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name of the called function/class."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _extract_remote_from_class(self, node: ast.ClassDef) -> dict[str, Any] | None:
        """Extract @remote decorator config from class definition."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                decorator_name = self._get_call_name(decorator)
                if decorator_name == "remote":
                    return self._parse_remote_config(decorator)
            elif isinstance(decorator, ast.Name) and decorator.id == "remote":
                return {}

        return None

    def _parse_remote_config(self, node: ast.Call) -> dict[str, Any]:
        """Parse @remote decorator arguments into config dict."""
        config: dict[str, Any] = {}

        # Parse keyword arguments
        for keyword in node.keywords:
            if keyword.arg:
                value = self._eval_node(keyword.value)
                if value is not None:
                    config[keyword.arg] = value

        # Parse positional argument (LiveServerless config object)
        if node.args:
            first_arg = node.args[0]

            # Check if it's a direct LiveServerless(...) call
            if isinstance(first_arg, ast.Call):
                serverless_config = self._parse_live_serverless(first_arg)
                if serverless_config:
                    config["serverless"] = serverless_config

            # Check if it's a variable reference (e.g., @remote(config))
            elif isinstance(first_arg, ast.Name):
                var_name = first_arg.id
                if var_name in self.config_variables:
                    config.update(self.config_variables[var_name])

        return config

    def _parse_live_serverless(self, node: ast.Call) -> dict[str, Any] | None:
        """Parse LiveServerless(...) configuration."""
        call_name = self._get_call_name(node)
        if call_name not in ("LiveServerless", "serverless"):
            return None

        config: dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg:
                value = self._eval_node(keyword.value)
                if value is not None:
                    config[keyword.arg] = value

        return config

    def _eval_node(self, node: ast.AST) -> Any:
        """Safely evaluate AST node to Python value."""
        try:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, (ast.Str, ast.Num)):
                return node.n if isinstance(node, ast.Num) else node.s
            elif isinstance(node, ast.List):
                return [self._eval_node(elt) for elt in node.elts]
            elif isinstance(node, ast.Dict):
                return {
                    self._eval_node(k): self._eval_node(v)
                    for k, v in zip(node.keys, node.values)
                    if k is not None
                }
            elif isinstance(node, ast.NameConstant):
                return node.value
            elif isinstance(node, ast.Attribute):
                # Handle enum attributes like ServerlessType.QB, GpuGroup.ADA_24
                return node.attr
        except Exception:
            pass
        return None


def parse_fastapi_file(
    file_path: Path,
) -> tuple[FastAPIAppInfo | None, dict[str, RouterInfo]]:
    """Parse a FastAPI Python file and extract app and router information.

    Args:
        file_path: Path to Python file containing FastAPI code

    Returns:
        Tuple of (FastAPIAppInfo, dict of RouterInfo by variable name)
    """
    source_code = file_path.read_text()
    parser = FastAPIASTParser(source_code)
    return parser.parse()


def parse_remote_configs(file_path: Path) -> dict[str, dict[str, Any]]:
    """Parse @remote decorator configurations from a worker file.

    Args:
        file_path: Path to Python file containing @remote decorated classes

    Returns:
        Dict mapping class names to their serverless configs
    """
    source_code = file_path.read_text()
    parser = RemoteDecoratorParser(source_code)
    return parser.extract_remote_configs()
