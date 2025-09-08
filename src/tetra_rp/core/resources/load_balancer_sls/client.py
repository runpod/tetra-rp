"""
LoadBalancerSls Client

This provides a way to work with LoadBalancerSls functionality by:
1. Supporting manual endpoint deployment
2. Providing dual-capability functionality (HTTP endpoints + remote execution)
3. Maintaining the core implementation that's already working
"""

import inspect
import logging
import asyncio
import aiohttp
from typing import List, Optional, Dict, Any

from .endpoint import scan_endpoint_methods
from tetra_rp.protos.remote_execution import FunctionRequest
from .serialization import SerializationUtils
from .exceptions import (
    LoadBalancerSlsError,
    LoadBalancerSlsConnectionError,
    LoadBalancerSlsAuthenticationError,
    LoadBalancerSlsExecutionError,
    LoadBalancerSlsConfigurationError,
)

log = logging.getLogger(__name__)


class LoadBalancerSls:
    """
    LoadBalancerSls client for dual-capability remote execution.

    Usage:
        # After manually deploying LoadBalancerSls container
        runtime = LoadBalancerSls("https://your-deployed-endpoint.com")

        @runtime.remote_class
        class MLModel:
            @endpoint(methods=['POST'])
            def predict(self, data):
                return result
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ):
        """
        Initialize LoadBalancerSls client.

        Args:
            endpoint_url: Base URL of deployed LoadBalancerSls container
                         e.g. "https://abc123-def456.rp.runpod.ai"
                         If None, will be loaded from config or environment
            api_key: RunPod API key for authentication (or set RUNPOD_API_KEY env var)
            **kwargs: Additional configuration parameters (timeout, max_retries, etc.)
        """
        import os

        # Simple initialization without complex config system
        self.endpoint_url = endpoint_url.rstrip("/") if endpoint_url else None
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if not self.endpoint_url:
            raise LoadBalancerSlsConfigurationError("endpoint_url is required")

        self._session = None
        self._health_checked = False
        self._health_check_retries = 3

        if not self.api_key:
            log.warning(
                "No API key provided. Set RUNPOD_API_KEY env var or pass api_key parameter."
            )

        log.info(f"LoadBalancerSls initialized with endpoint: {self.endpoint_url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with authentication headers."""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Simple timeout configuration like the original
            timeout = aiohttp.ClientTimeout(total=self.timeout)

            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        operation_name: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic and proper error handling."""
        session = await self._get_session()
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if method.upper() == "GET":
                    async with session.get(url) as response:
                        return await self._handle_response(response, operation_name)
                else:
                    async with session.post(url, json=json_data) as response:
                        return await self._handle_response(response, operation_name)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt == self.max_retries:
                    break

                wait_time = self.retry_delay * (2**attempt)  # Exponential backoff
                log.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

        # If we get here, all retries failed
        raise LoadBalancerSlsConnectionError(
            self.endpoint_url,
            f"Failed after {self.max_retries + 1} attempts: {last_exception}",
            {"operation": operation_name, "last_error": str(last_exception)},
        )

    async def _handle_response(
        self, response: aiohttp.ClientResponse, operation_name: str
    ) -> Dict[str, Any]:
        """Handle HTTP response with proper error checking."""
        try:
            if response.status == 401:
                raise LoadBalancerSlsAuthenticationError(
                    "Invalid API key or authentication failed"
                )
            elif response.status == 404:
                raise LoadBalancerSlsConnectionError(
                    self.endpoint_url,
                    "Endpoint not found - check your endpoint URL",
                    {"status_code": response.status, "operation": operation_name},
                )
            elif response.status >= 400:
                error_text = await response.text()
                raise LoadBalancerSlsConnectionError(
                    self.endpoint_url,
                    f"HTTP {response.status}: {error_text}",
                    {"status_code": response.status, "operation": operation_name},
                )

            response.raise_for_status()
            return await response.json()

        except aiohttp.ContentTypeError as e:
            raise LoadBalancerSlsConnectionError(
                self.endpoint_url,
                f"Invalid JSON response: {e}",
                {"operation": operation_name},
            )
        except Exception as e:
            if isinstance(
                e,
                (
                    LoadBalancerSlsAuthenticationError,
                    LoadBalancerSlsConnectionError,
                ),
            ):
                raise
            raise LoadBalancerSlsConnectionError(
                self.endpoint_url,
                f"Unexpected error handling response: {e}",
                {"operation": operation_name},
            )

    def remote_class(
        self,
        dependencies: Optional[List[str]] = None,
        system_dependencies: Optional[List[str]] = None,
    ):
        """
        Decorator for LoadBalancerSls classes.

        Args:
            dependencies: Python packages to install
            system_dependencies: System packages to install
        """

        def decorator(cls):
            return DeploymentClassWrapper(
                cls=cls,
                runtime=self,
                dependencies=dependencies or [],
                system_dependencies=system_dependencies or [],
            )

        return decorator

    async def call_remote_method(self, request: FunctionRequest) -> Any:
        """Call remote method via /execute endpoint."""
        try:
            # Ensure endpoint is healthy before making the request
            await self._ensure_healthy()
            
            url = f"{self.endpoint_url}/execute"
            payload = {"input": request.model_dump(exclude_none=True)}

            log.debug(f"Remote call to {url} for method: {request.method_name}")

            result = await self._make_request_with_retry(
                "POST", url, f"remote_execution_{request.method_name}", payload
            )

            if not result.get("success"):
                error_msg = result.get("error", "Unknown execution error")
                raise LoadBalancerSlsExecutionError(
                    request.method_name, error_msg, {"result": result}
                )

            # Deserialize result
            if result.get("result"):
                try:
                    return SerializationUtils.deserialize_result(result["result"])
                except Exception as e:
                    raise LoadBalancerSlsError(
                        f"Failed to deserialize result from {request.method_name}: {e}",
                        {"serialization_error": str(e)},
                    )
            return None

        except (
            LoadBalancerSlsConnectionError,
            LoadBalancerSlsExecutionError,
            LoadBalancerSlsError,
        ):
            raise
        except Exception as e:
            raise LoadBalancerSlsError(
                f"Unexpected error in remote method call: {e}",
                {"method_name": request.method_name, "error": str(e)},
            )

    async def call_http_endpoint(self, method_name: str, data: Dict[str, Any]) -> Any:
        """Call HTTP endpoint directly."""
        try:
            # Ensure endpoint is healthy before making the request
            await self._ensure_healthy()
            
            url = f"{self.endpoint_url}/{method_name}"

            log.debug(f"HTTP call to {url} for method: {method_name}")

            result = await self._make_request_with_retry(
                "POST", url, f"http_endpoint_{method_name}", data
            )

            return result

        except LoadBalancerSlsConnectionError:
            raise
        except Exception as e:
            raise LoadBalancerSlsError(
                f"Unexpected error in HTTP endpoint call: {e}",
                {"method_name": method_name, "error": str(e)},
            )

    async def _ensure_healthy(self) -> None:
        """Ensure the endpoint is healthy before making requests."""
        if self._health_checked:
            return
        
        log.debug("Performing automatic health check...")
        
        for attempt in range(self._health_check_retries):
            try:
                await self._perform_health_check()
                self._health_checked = True
                log.debug(f"Health check successful on attempt {attempt + 1}")
                return
            except Exception as e:
                if attempt == self._health_check_retries - 1:
                    log.error(f"Health check failed after {self._health_check_retries} attempts: {e}")
                    raise LoadBalancerSlsConnectionError(
                        self.endpoint_url,
                        f"Endpoint health check failed after {self._health_check_retries} attempts: {e}",
                        {'attempts': self._health_check_retries, 'last_error': str(e)}
                    )
                else:
                    log.warning(f"Health check attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(1.0 * (attempt + 1))  # Progressive backoff
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform a single health check."""
        url = f"{self.endpoint_url}/health"
        log.debug(f"Health check: {url}")
        return await self._make_request_with_retry("GET", url, "health_check")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check LoadBalancerSls health (public method)."""
        try:
            return await self._perform_health_check()
        except LoadBalancerSlsConnectionError:
            raise
        except Exception as e:
            raise LoadBalancerSlsError(
                f"Unexpected error during health check: {e}", {"error": str(e)}
            )

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class DeploymentClassWrapper:
    """Class wrapper for LoadBalancerSls."""

    def __init__(
        self,
        cls,
        runtime: LoadBalancerSls,
        dependencies: List[str],
        system_dependencies: List[str],
    ):
        self._original_class = cls
        self._runtime = runtime
        self._dependencies = dependencies
        self._system_dependencies = system_dependencies

        # Scan for @endpoint methods
        self._endpoint_methods = scan_endpoint_methods(cls)

        log.info(f"Created deployment wrapper for {cls.__name__}")
        log.info(
            f"Found {len(self._endpoint_methods)} endpoint methods: {list(self._endpoint_methods.keys())}"
        )

    def __call__(self, *args, **kwargs):
        """Create instance wrapper when class is instantiated."""
        return DeploymentInstanceWrapper(
            wrapper=self, constructor_args=args, constructor_kwargs=kwargs
        )


class DeploymentInstanceWrapper:
    """Instance wrapper for method calls."""

    def __init__(
        self,
        wrapper: DeploymentClassWrapper,
        constructor_args: tuple,
        constructor_kwargs: dict,
    ):
        self._wrapper = wrapper
        self._constructor_args = constructor_args
        self._constructor_kwargs = constructor_kwargs
        self._instance_id = f"{wrapper._original_class.__name__}_deployment"

    def __getattr__(self, name: str):
        """Route method calls to appropriate interface."""

        if name in self._wrapper._endpoint_methods:
            # HTTP endpoint method
            return self._create_http_proxy(name)
        else:
            # Remote execution method
            return self._create_remote_proxy(name)

    def _create_http_proxy(self, method_name: str):
        """Create HTTP method proxy."""

        async def http_proxy(*args, **kwargs):
            try:
                # Convert args to kwargs
                if args:
                    method_sig = inspect.signature(
                        getattr(self._wrapper._original_class, method_name)
                    )
                    param_names = list(method_sig.parameters.keys())[1:]  # Skip 'self'
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            kwargs[param_names[i]] = arg

                return await self._wrapper._runtime.call_http_endpoint(
                    method_name, kwargs
                )

            except Exception as e:
                if isinstance(e, LoadBalancerSlsError):
                    raise
                raise LoadBalancerSlsError(
                    f"Error in HTTP proxy for {method_name}: {e}",
                    {
                        "method_name": method_name,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    },
                )

        return http_proxy

    def _create_remote_proxy(self, method_name: str):
        """Create remote execution proxy."""

        async def remote_proxy(*args, **kwargs):
            try:
                # Create class execution request
                request = self._create_function_request(method_name, args, kwargs)
                return await self._wrapper._runtime.call_remote_method(request)

            except Exception as e:
                if isinstance(e, LoadBalancerSlsError):
                    raise
                raise LoadBalancerSlsError(
                    f"Error in remote proxy for {method_name}: {e}",
                    {
                        "method_name": method_name,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    },
                )

        return remote_proxy

    def _create_function_request(
        self, method_name: str, args: tuple, kwargs: dict
    ) -> FunctionRequest:
        """Create FunctionRequest for remote execution."""
        try:
            import textwrap

            # Get class source and clean it
            class_source = inspect.getsource(self._wrapper._original_class)
            clean_class_code = textwrap.dedent(class_source)

            # Remove @remote and @runtime.remote_class decorator lines
            lines = clean_class_code.split("\n")
            cleaned_lines = []
            skip_next = False

            for line in lines:
                stripped = line.strip()
                # Skip @remote(...) and @runtime.remote_class decorators
                if stripped.startswith("@") and (
                    "remote_class" in stripped
                    or stripped.startswith("@remote(")
                    or stripped == "@remote"
                ):
                    skip_next = True
                    continue
                elif skip_next and stripped == "":
                    skip_next = False
                    continue
                elif skip_next and stripped.startswith("class"):
                    skip_next = False
                    cleaned_lines.append(line)
                elif not skip_next:
                    cleaned_lines.append(line)

            clean_class_code = "\n".join(cleaned_lines)

            # Serialize arguments with error handling
            try:
                serialized_args = [
                    SerializationUtils.serialize_result(arg) for arg in args
                ]
                serialized_kwargs = {
                    k: SerializationUtils.serialize_result(v) for k, v in kwargs.items()
                }

                # Serialize constructor arguments
                constructor_args = [
                    SerializationUtils.serialize_result(arg)
                    for arg in self._constructor_args
                ]
                constructor_kwargs = {
                    k: SerializationUtils.serialize_result(v)
                    for k, v in self._constructor_kwargs.items()
                }
            except Exception as e:
                raise LoadBalancerSlsError(
                    f"Failed to serialize arguments for {method_name}: {e}",
                    {"method_name": method_name, "serialization_error": str(e)},
                )

            return FunctionRequest(
                execution_type="class",
                class_name=self._wrapper._original_class.__name__,
                class_code=clean_class_code,
                method_name=method_name,
                args=serialized_args,
                kwargs=serialized_kwargs,
                constructor_args=constructor_args,
                constructor_kwargs=constructor_kwargs,
                dependencies=self._wrapper._dependencies,
                system_dependencies=self._wrapper._system_dependencies,
                instance_id=self._instance_id,
                create_new_instance=True,
            )

        except Exception as e:
            if isinstance(e, LoadBalancerSlsError):
                raise
            raise LoadBalancerSlsError(
                f"Failed to create function request for {method_name}: {e}",
                {"method_name": method_name, "error": str(e)},
            )
