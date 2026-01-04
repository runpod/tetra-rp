"""LoadBalancerSlsStub - Stub for load-balanced serverless execution.

Enables @remote decorator to work with LoadBalancerSlsResource endpoints
via direct HTTP calls instead of queue-based job submission.
"""

import base64
import logging
import httpx
import cloudpickle

from .live_serverless import get_function_source

log = logging.getLogger(__name__)


class LoadBalancerSlsStub:
    """HTTP-based stub for load-balanced serverless endpoint execution.

    Differs from LiveServerlessStub:
    - Direct HTTP POST to /execute endpoint (not queue-based)
    - No job ID polling
    - Synchronous HTTP response
    - Same function serialization pattern (cloudpickle + base64)
    """

    def __init__(self, server):
        """Initialize stub with LoadBalancerSlsResource server.

        Args:
            server: LoadBalancerSlsResource instance
        """
        self.server = server

    async def __call__(
        self, func, dependencies, system_dependencies, accelerate_downloads, *args, **kwargs
    ):
        """Execute function on load-balanced endpoint.

        Args:
            func: Function to execute
            dependencies: Pip dependencies required
            system_dependencies: System dependencies required
            accelerate_downloads: Whether to accelerate downloads
            *args: Function positional arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result (deserialized from cloudpickle)

        Raises:
            Exception: If endpoint returns error or HTTP call fails
        """
        # 1. Prepare request (serialize function + args)
        request = self._prepare_request(
            func, dependencies, system_dependencies, accelerate_downloads, *args, **kwargs
        )

        # 2. Execute via HTTP POST to endpoint
        response = await self._execute_function(request)

        # 3. Deserialize and return result
        return self._handle_response(response)

    def _prepare_request(
        self, func, dependencies, system_dependencies, accelerate_downloads, *args, **kwargs
    ) -> dict:
        """Prepare HTTP request payload.

        Extracts function source code and serializes arguments using cloudpickle.

        Args:
            func: Function to serialize
            dependencies: Pip dependencies
            system_dependencies: System dependencies
            accelerate_downloads: Download acceleration flag
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Request dictionary with serialized function and arguments
        """
        source, _ = get_function_source(func)

        request = {
            "function_name": func.__name__,
            "function_code": source,
            "dependencies": dependencies or [],
            "system_dependencies": system_dependencies or [],
            "accelerate_downloads": accelerate_downloads,
        }

        # Serialize arguments using cloudpickle + base64
        if args:
            request["args"] = [
                base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8") for arg in args
            ]
        if kwargs:
            request["kwargs"] = {
                k: base64.b64encode(cloudpickle.dumps(v)).decode("utf-8")
                for k, v in kwargs.items()
            }

        return request

    async def _execute_function(self, request: dict) -> dict:
        """Execute function via direct HTTP POST to endpoint.

        Posts serialized function and arguments to /execute endpoint.
        No job ID polling - waits for synchronous HTTP response.

        Args:
            request: Request dictionary with function_code, args, kwargs

        Returns:
            Response dictionary with success flag and result

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If endpoint_url not available
        """
        if not self.server.endpoint_url:
            raise ValueError("Endpoint URL not available - endpoint may not be deployed")

        execute_url = f"{self.server.endpoint_url}/execute"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(execute_url, json=request)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Execution timeout on {self.server.name} after 30s: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"HTTP error from endpoint {self.server.name}: "
                f"{e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ConnectionError(
                f"Failed to connect to endpoint {self.server.name} ({execute_url}): {e}"
            ) from e

    def _handle_response(self, response: dict):
        """Deserialize and validate response.

        Args:
            response: Response dictionary from endpoint

        Returns:
            Deserialized function result

        Raises:
            ValueError: If response format is invalid
            Exception: If response indicates error
        """
        if not isinstance(response, dict):
            raise ValueError(f"Invalid response type: {type(response)}")

        if response.get("success"):
            result_b64 = response.get("result")
            if result_b64 is None:
                raise ValueError("Response marked success but result is None")

            try:
                return cloudpickle.loads(base64.b64decode(result_b64))
            except Exception as e:
                raise ValueError(f"Failed to deserialize result: {e}") from e
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Remote execution failed: {error}")
