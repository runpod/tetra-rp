"""
HTTP Endpoint decorator for Runtime Two

This module provides the @endpoint decorator that marks class methods
for HTTP endpoint exposure in Runtime Two.
"""

from typing import List, Optional, Dict, Any, Callable
from functools import wraps


def endpoint(methods: List[str] = ["POST"], route: Optional[str] = None) -> Callable:
    """
    Decorator to mark class methods as HTTP endpoints in DeploymentRuntime.

    Args:
        methods: List of HTTP methods supported (GET, POST, PUT, DELETE, etc.)
        route: Custom route path. If None, uses "/{method_name}"

    Raises:
        ValueError: If methods is empty or contains invalid HTTP methods
        TypeError: If methods is not a list or route is not a string

    Example:
        @endpoint(methods=['GET', 'POST'])
        def predict(self, data):
            return self.model.predict(data)

        @endpoint(methods=['GET'], route='/health-check')
        def health(self):
            return {"status": "healthy"}
    """
    # Input validation
    if not isinstance(methods, list):
        raise TypeError("methods must be a list")

    if not methods:
        raise ValueError("methods cannot be empty")

    if route is not None and not isinstance(route, str):
        raise TypeError("route must be a string or None")

    # Validate HTTP methods
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    invalid_methods = [m for m in methods if m.upper() not in valid_methods]
    if invalid_methods:
        raise ValueError(
            f"Invalid HTTP methods: {invalid_methods}. Valid methods: {valid_methods}"
        )

    def decorator(func: Callable) -> Callable:
        if not callable(func):
            raise TypeError(
                "endpoint decorator can only be applied to callable objects"
            )

        # Attach endpoint configuration to the method
        func._endpoint_config = {
            "methods": [m.upper() for m in methods],  # Normalize to uppercase
            "route": route or f"/{func.__name__}",
        }

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Copy the endpoint config to the wrapper
        wrapper._endpoint_config = func._endpoint_config

        return wrapper

    return decorator


def scan_endpoint_methods(cls) -> Dict[str, Dict[str, Any]]:
    """
    Scan a class for methods decorated with @endpoint.

    Args:
        cls: Class to scan

    Returns:
        Dict mapping method names to their endpoint configurations

    Raises:
        TypeError: If cls is not a class
    """
    import inspect

    if not inspect.isclass(cls):
        raise TypeError("cls must be a class")

    endpoint_methods: Dict[str, Dict[str, Any]] = {}

    # Scan both functions and methods (bound and unbound)
    for name, method in inspect.getmembers(
        cls, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
    ):
        if hasattr(method, "_endpoint_config"):
            config = method._endpoint_config
            # Validate configuration structure
            if (
                not isinstance(config, dict)
                or "methods" not in config
                or "route" not in config
            ):
                continue
            endpoint_methods[name] = config

    return endpoint_methods
