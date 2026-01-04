"""Factory for creating FastAPI load-balanced handlers.

This module provides the factory function for generating FastAPI applications
that handle load-balanced serverless endpoints. It supports both user-defined
HTTP routes and the framework's /execute endpoint for @remote function execution.

Security Model:
    The /execute endpoint accepts and executes serialized function code. This is
    secure because:
    1. The function code originates from the client's @remote decorator
    2. The client (user) controls what function gets sent
    3. This mirrors the trusted client model of LiveServerlessStub
    4. In production, API authentication should protect the /execute endpoint

    Users should NOT expose the /execute endpoint to untrusted clients.
"""

import base64
import inspect
import logging
from typing import Any, Callable, Dict

import cloudpickle
from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


def create_lb_handler(route_registry: Dict[tuple[str, str], Callable]) -> FastAPI:
    """Create FastAPI app with routes from registry.

    Args:
        route_registry: Mapping of (HTTP_METHOD, path) -> handler_function
                       Example: {("GET", "/api/health"): health_check}

    Returns:
        Configured FastAPI application with routes registered.
    """
    app = FastAPI(title="Flash Load-Balanced Handler")

    # Register /execute endpoint for @remote stub execution
    @app.post("/execute")
    async def execute_remote_function(request: Request) -> Dict[str, Any]:
        """Framework endpoint for @remote decorator execution.

        WARNING: This endpoint is INTERNAL to the Flash framework. It should only be
        called by the @remote stub from tetra_rp.stubs.load_balancer_sls. Exposing
        this endpoint to untrusted clients could allow arbitrary code execution.

        Accepts serialized function code and arguments, executes them,
        and returns serialized result.

        Request body:
            {
                "function_name": "process_data",
                "function_code": "def process_data(x, y): return x + y",
                "args": [base64_encoded_arg1, base64_encoded_arg2],
                "kwargs": {"key": base64_encoded_value}
            }

        Returns:
            {
                "success": true,
                "result": base64_encoded_result
            }
            or
            {
                "success": false,
                "error": "error message"
            }
        """
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse request body: {e}")
            return {"success": False, "error": f"Invalid request body: {e}"}

        try:
            # Extract function metadata
            function_name = body.get("function_name")
            function_code = body.get("function_code")

            if not function_name or not function_code:
                return {
                    "success": False,
                    "error": "Missing function_name or function_code in request",
                }

            # Deserialize arguments
            args = []
            for arg_b64 in body.get("args", []):
                try:
                    arg = cloudpickle.loads(base64.b64decode(arg_b64))
                    args.append(arg)
                except Exception as e:
                    logger.error(f"Failed to deserialize argument: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to deserialize argument: {e}",
                    }

            kwargs = {}
            for key, val_b64 in body.get("kwargs", {}).items():
                try:
                    val = cloudpickle.loads(base64.b64decode(val_b64))
                    kwargs[key] = val
                except Exception as e:
                    logger.error(f"Failed to deserialize kwarg '{key}': {e}")
                    return {
                        "success": False,
                        "error": f"Failed to deserialize kwarg '{key}': {e}",
                    }

            # Execute function in isolated namespace
            namespace: Dict[str, Any] = {}
            try:
                exec(function_code, namespace)
            except SyntaxError as e:
                logger.error(f"Syntax error in function code: {e}")
                return {
                    "success": False,
                    "error": f"Syntax error in function code: {e}",
                }
            except Exception as e:
                logger.error(f"Error executing function code: {e}")
                return {
                    "success": False,
                    "error": f"Error executing function code: {e}",
                }

            # Get function from namespace
            if function_name not in namespace:
                return {
                    "success": False,
                    "error": f"Function '{function_name}' not found in executed code",
                }

            func = namespace[function_name]

            # Execute function
            try:
                result = func(*args, **kwargs)

                # Handle async functions
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as e:
                logger.error(f"Function execution failed: {e}")
                return {
                    "success": False,
                    "error": f"Function execution failed: {e}",
                }

            # Serialize result
            try:
                result_b64 = base64.b64encode(cloudpickle.dumps(result)).decode("utf-8")
                return {"success": True, "result": result_b64}
            except Exception as e:
                logger.error(f"Failed to serialize result: {e}")
                return {
                    "success": False,
                    "error": f"Failed to serialize result: {e}",
                }

        except Exception as e:
            logger.error(f"Unexpected error in /execute endpoint: {e}")
            return {"success": False, "error": f"Unexpected error: {e}"}

    # Register user-defined routes from registry
    for (method, path), handler in route_registry.items():
        method_upper = method.upper()

        if method_upper == "GET":
            app.get(path)(handler)
        elif method_upper == "POST":
            app.post(path)(handler)
        elif method_upper == "PUT":
            app.put(path)(handler)
        elif method_upper == "DELETE":
            app.delete(path)(handler)
        elif method_upper == "PATCH":
            app.patch(path)(handler)
        else:
            logger.warning(
                f"Unsupported HTTP method '{method}' for path '{path}'. Skipping."
            )

    return app
