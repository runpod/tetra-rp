"""Production wrapper for cross-endpoint function routing."""

import base64
import logging
from typing import Any, Callable, Dict, Optional

import cloudpickle

from .service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ProductionWrapper:
    """Wrapper that routes function execution between endpoints.

    Intercepts stub execution and determines if the call is local (execute
    directly) or remote (call via HTTP to another endpoint).
    """

    def __init__(self, service_registry: ServiceRegistry):
        """Initialize production wrapper.

        Args:
            service_registry: Service registry for routing decisions.
        """
        self.service_registry = service_registry
        self._directory_loaded = False

    async def wrap_function_execution(
        self,
        original_stub_func: Callable,
        func: Callable,
        dependencies: Optional[list],
        system_dependencies: Optional[list],
        accelerate_downloads: bool,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Route function execution to local or remote endpoint.

        Args:
            original_stub_func: The original stubbed_resource function.
            func: The decorated function being called.
            dependencies: Pip dependencies (for local execution).
            system_dependencies: System dependencies (for local execution).
            accelerate_downloads: Download acceleration flag (for local).
            *args: Function positional arguments.
            **kwargs: Function keyword arguments.

        Returns:
            Function execution result.

        Raises:
            Exception: If execution fails.
        """
        function_name = func.__name__

        # Ensure directory is loaded
        await self.service_registry._ensure_directory_loaded()

        # Determine routing
        try:
            resource = self.service_registry.get_resource_for_function(function_name)
        except ValueError as e:
            # Function not in manifest, execute locally
            logger.debug(
                f"Function {function_name} not in manifest: {e}, executing locally"
            )
            return await original_stub_func(
                func,
                dependencies,
                system_dependencies,
                accelerate_downloads,
                *args,
                **kwargs,
            )

        # Local execution
        if resource is None:
            logger.debug(f"Executing local function: {function_name}")
            return await original_stub_func(
                func,
                dependencies,
                system_dependencies,
                accelerate_downloads,
                *args,
                **kwargs,
            )

        # Remote execution
        logger.debug(f"Routing function {function_name} to remote endpoint")
        return await self._execute_remote(
            resource,
            function_name,
            args,
            kwargs,
            execution_type="function",
        )

    async def wrap_class_method_execution(
        self,
        original_method_func: Callable,
        request: Any,
    ) -> Any:
        """Route class method execution to local or remote endpoint.

        Args:
            original_method_func: The original execute_class_method function.
            request: FunctionRequest containing class and method info.

        Returns:
            Method execution result.

        Raises:
            Exception: If execution fails.
        """
        # Ensure directory is loaded
        await self.service_registry._ensure_directory_loaded()

        class_name = getattr(request, "class_name", None)

        if not class_name:
            # No class name, execute locally
            return await original_method_func(request)

        # Determine routing
        try:
            resource = self.service_registry.get_resource_for_function(class_name)
        except ValueError:
            # Class not in manifest, execute locally
            logger.debug(f"Class {class_name} not in manifest, executing locally")
            return await original_method_func(request)

        # Local execution
        if resource is None:
            logger.debug(f"Executing local class method: {class_name}")
            return await original_method_func(request)

        # Remote execution
        logger.debug(f"Routing class {class_name} to remote endpoint")

        # Convert FunctionRequest to dict payload
        payload = self._build_class_payload(request)
        return await self._execute_remote(
            resource,
            class_name,
            (),
            payload.get("input", {}),
            execution_type="class",
        )

    async def _execute_remote(
        self,
        resource,
        function_name: str,
        args: tuple,
        kwargs: dict,
        execution_type: str,
    ) -> Any:
        """Execute function on remote endpoint.

        Args:
            resource: ServerlessResource with endpoint ID set.
            function_name: Name of function/class to execute.
            args: Positional arguments.
            kwargs: Keyword arguments.
            execution_type: "function" or "class".

        Returns:
            Execution result.

        Raises:
            Exception: If execution fails.
        """
        # Serialize arguments
        serialized_args = [
            base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8") for arg in args
        ]
        serialized_kwargs = {
            k: base64.b64encode(cloudpickle.dumps(v)).decode("utf-8")
            for k, v in kwargs.items()
        }

        # Build payload matching RunPod format
        payload = {
            "input": {
                "function_name": function_name,
                "execution_type": execution_type,
                "args": serialized_args,
                "kwargs": serialized_kwargs,
            }
        }

        # Execute via ServerlessResource
        result = await resource.run_sync(payload)

        # Handle response
        if not result.success:
            error = getattr(result, "error", "Unknown error")
            raise Exception(f"Remote execution of {function_name} failed: {error}")

        return result.output

    def _build_class_payload(self, request: Any) -> Dict[str, Any]:
        """Build payload from FunctionRequest for class execution.

        Args:
            request: FunctionRequest object.

        Returns:
            RunPod-format payload dict.
        """
        # Extract request data - handle both dict and object access patterns
        if isinstance(request, dict):
            data = request
        else:
            data = (
                request.model_dump(exclude_none=True)
                if hasattr(request, "model_dump")
                else {}
            )

        # Extract class execution data
        payload = {
            "input": {
                "function_name": data.get("class_name"),
                "execution_type": "class",
                "args": data.get("args", []),
                "kwargs": data.get("kwargs", {}),
                "method_name": data.get("method_name"),
            }
        }

        return payload


# Singleton instance management
_wrapper_instance: Optional[ProductionWrapper] = None


def create_production_wrapper(
    service_registry: Optional[ServiceRegistry] = None,
) -> ProductionWrapper:
    """Create or get singleton ProductionWrapper instance.

    Args:
        service_registry: Service registry. Creates if not provided.

    Returns:
        ProductionWrapper instance.
    """
    global _wrapper_instance

    if _wrapper_instance is None:
        # Create components if not provided
        if service_registry is None:
            service_registry = ServiceRegistry()

        _wrapper_instance = ProductionWrapper(service_registry)

    return _wrapper_instance


def reset_wrapper() -> None:
    """Reset singleton wrapper (mainly for testing)."""
    global _wrapper_instance
    _wrapper_instance = None
