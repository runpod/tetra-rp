"""Factory for creating FastAPI load-balanced handlers.

This module provides the factory function for generating FastAPI applications
that handle load-balanced serverless endpoints. It supports:
- User-defined HTTP routes
- /execute endpoint for @remote function execution (LiveLoadBalancer only)
- /manifest endpoint for mothership service discovery (when FLASH_IS_MOTHERSHIP=true)

Security Model:
    The /execute endpoint accepts and executes serialized function code. This is
    secure because:
    1. The function code originates from the client's @remote decorator
    2. The client (user) controls what function gets sent
    3. This mirrors the trusted client model of LiveServerlessStub
    4. In production, API authentication should protect the /execute endpoint

    Users should NOT expose the /execute endpoint to untrusted clients.

    The /manifest endpoint returns deployment metadata and is safe to expose
    publicly as it contains only structural information about deployed functions.
"""

import inspect
import logging
import os
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .manifest_fetcher import ManifestFetcher
from .serialization import (
    deserialize_args,
    deserialize_kwargs,
    serialize_arg,
)

logger = logging.getLogger(__name__)

# Module-level manifest fetcher (singleton, reused across requests)
_manifest_fetcher: Optional[ManifestFetcher] = None


def _get_manifest_fetcher() -> ManifestFetcher:
    """Get or create the manifest fetcher singleton."""
    global _manifest_fetcher
    if _manifest_fetcher is None:
        _manifest_fetcher = ManifestFetcher()
    return _manifest_fetcher


def create_lb_handler(
    route_registry: Dict[tuple[str, str], Callable], include_execute: bool = False
) -> FastAPI:
    """Create FastAPI app with routes from registry.

    Args:
        route_registry: Mapping of (HTTP_METHOD, path) -> handler_function
                       Example: {("GET", "/api/health"): health_check}
        include_execute: Whether to register /execute endpoint for @remote execution.
                        Only used for LiveLoadBalancer (local development).
                        Deployed endpoints should not expose /execute for security.

    Returns:
        Configured FastAPI application with routes registered.
    """
    app = FastAPI(title="Flash Load-Balanced Handler")

    # Register /execute endpoint for @remote stub execution (if enabled)
    if include_execute:

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
                try:
                    args = deserialize_args(body.get("args", []))
                    kwargs = deserialize_kwargs(body.get("kwargs", {}))
                except Exception as e:
                    logger.error(f"Failed to deserialize arguments: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to deserialize arguments: {e}",
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
                    result_b64 = serialize_arg(result)
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

    # Register /manifest endpoint for mothership discovery (if enabled)
    if os.getenv("FLASH_IS_MOTHERSHIP", "").lower() == "true":

        @app.get("/manifest")
        async def get_manifest() -> JSONResponse:
            """Mothership discovery endpoint.

            Fetches manifest from RunPod GraphQL API (source of truth), caches it
            locally, and serves to child endpoints. Falls back to local file if
            RunPod API is unavailable.

            Only available when FLASH_IS_MOTHERSHIP=true environment variable is set.

            Returns:
                JSONResponse with manifest content or 404 if not found
            """
            fetcher = _get_manifest_fetcher()
            mothership_id = os.getenv("RUNPOD_ENDPOINT_ID")

            # Fetch manifest (from cache, RunPod GQL, or local file)
            manifest_dict = await fetcher.get_manifest(mothership_id)

            if not manifest_dict or not manifest_dict.get("resources"):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "Manifest not found",
                        "detail": "Could not load manifest from RunPod or local file",
                    },
                )

            return JSONResponse(status_code=200, content=manifest_dict)

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
