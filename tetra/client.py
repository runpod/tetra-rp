import base64
import cloudpickle
from typing import Union, List

from . import remote_execution_pb2
from . import remote_execution_pb2_grpc
import random
import grpc.aio
from functools import wraps
from .resource_manager import ResourceManager
from .core.resources import ServerlessResource
from .core.utils.singleton import SingletonMixin


def get_function_source(func):
    """Extract the function source code without the decorator."""
    import ast
    import inspect
    import textwrap

    # Get the source code of the decorated function
    source = inspect.getsource(func)

    # Parse the source code
    module = ast.parse(source)

    # Find the function definition node
    function_def = None
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == func.__name__:
            function_def = node
            break

    if not function_def:
        raise ValueError(f"Could not find function definition for {func.__name__}")

    # Get the line and column offsets
    lineno = function_def.lineno - 1  # Line numbers are 1-based
    col_offset = function_def.col_offset

    # Split into lines and extract just the function part
    lines = source.split("\n")
    function_lines = lines[lineno:]

    # Dedent to remove any extra indentation
    function_source = textwrap.dedent("\n".join(function_lines))

    return function_source


class RunPodServerlessStub:
    """Adapter class to make RunPod endpoints look like gRPC stubs."""

    def __init__(self, endpoint_url):
        import runpod
        import os

        # Set RunPod API key
        api_key = os.environ.get("RUNPOD_API_KEY")
        if not api_key:
            raise ValueError("RUNPOD_API_KEY environment variable is not set")

        runpod.api_key = api_key

        self.endpoint_url = endpoint_url
        # Extract endpoint ID from URL
        self.endpoint_id = endpoint_url.strip("/").split("/")[-1]
        print(
            f"Initialized RunPod stub for endpoint: {endpoint_url} (ID: {self.endpoint_id})"
        )

        # Initialize the RunPod endpoint
        self.endpoint = runpod.Endpoint(self.endpoint_id)

    async def ExecuteFunction(self, request):
        """
        Execute function on RunPod serverless endpoint using the RunPod SDK.
        Waits for the job to complete using the SDK's built-in timeout mechanism.
        """
        import base64
        import cloudpickle
        import asyncio

        # Convert the gRPC request to RunPod format
        payload = {
            "function_name": request.function_name,
            "function_code": request.function_code,
            "args": [arg for arg in request.args],  # Convert to regular list
            "kwargs": {
                k: v for k, v in request.kwargs.items()
            },  # Convert to regular dict
        }

        # Add dependencies if specified
        if hasattr(request, "dependencies") and request.dependencies:
            payload["dependencies"] = [dep for dep in request.dependencies]

        print(f"Executing function on RunPod endpoint ID: {self.endpoint_id}")

        try:
            # Run using the RunPod SDK (non-async)
            loop = asyncio.get_event_loop()
            run_request = await loop.run_in_executor(
                None, lambda: self.endpoint.run({"input": payload})
            )

            # print(f"Job submitted with ID: {run_request.id}")

            # Initial status check without blocking
            status = await loop.run_in_executor(None, lambda: run_request.status())

            print(f"Initial job status: {status}")

            # Wait for completion with timeout
            if status != "COMPLETED":
                output = await loop.run_in_executor(
                    None,
                    lambda: run_request.output(timeout=300),  # 5 minute timeout
                )
            else:
                output = await loop.run_in_executor(None, lambda: run_request.output())

            print(f"Job completed, output received")

            # Process the output
            if isinstance(output, dict) and "success" in output:
                if output["success"]:
                    return remote_execution_pb2.FunctionResponse(
                        success=True, result=output.get("result", "")
                    )
                else:
                    return remote_execution_pb2.FunctionResponse(
                        success=False, error=output.get("error", "Unknown error")
                    )
            else:
                # Direct output from RunPod
                serialized_result = base64.b64encode(cloudpickle.dumps(output)).decode(
                    "utf-8"
                )
                return remote_execution_pb2.FunctionResponse(
                    success=True, result=serialized_result
                )

        except Exception as e:
            import traceback

            error_traceback = traceback.format_exc()
            print(f"Exception during RunPod execution: {str(e)}\n{error_traceback}")
            return remote_execution_pb2.FunctionResponse(
                success=False, error=f"RunPod request failed: {str(e)}"
            )


class RemoteExecutionClient(SingletonMixin):
    def __init__(self):
        self.servers = {}
        self.stubs = {}
        self.pools = {}
        self.resource_manager = ResourceManager()

    async def add_server(self, name: str, address: str):
        """Register a new server"""
        self.servers[name] = address
        channel = grpc.aio.insecure_channel(address)
        self.stubs[name] = remote_execution_pb2_grpc.RemoteExecutorStub(channel)

    async def add_runpod_server(self, name: str, endpoint_url: str):
        """Register a RunPod serverless endpoint"""
        # For RunPod, we'll store the endpoint URL in a format that indicates it's a RunPod endpoint
        self.servers[name] = f"runpod:{endpoint_url}"

        # Create a custom stub for RunPod that will handle the different protocol
        self.stubs[name] = RunPodServerlessStub(endpoint_url)

    def create_pool(self, pool_name: str, server_names: List[str]):
        if not all(name in self.servers for name in server_names):
            raise ValueError("All servers must be registered first")
        self.pools[pool_name] = server_names

    def get_stub(
        self,
        server_spec: Union[str, List[str]],
        fallback: Union[None, str, List[str]] = None,
    ):
        if isinstance(server_spec, list):
            return self._get_pool_stub(server_spec)
        elif server_spec in self.pools:
            return self._get_pool_stub(self.pools[server_spec])
        elif server_spec in self.stubs:
            stub = self.stubs[server_spec]
            if fallback:
                return StubWithFallback(stub, self, fallback)
            return stub
        else:
            raise ValueError(f"Unknown server or pool: {server_spec}")

    def _get_pool_stub(self, server_names: List[str]):
        if not server_names:
            raise ValueError("Server pool is empty")
        server_name = random.choice(server_names)
        return self.stubs[server_name]

    # Get resources in the pool
    def get_pool(self, pool_name: str):
        return self.pools[pool_name]

    def get_server(self, server_name: str):
        return self.servers[server_name]


class StubWithFallback:
    def __init__(self, primary_stub, client, fallback_spec):
        self.primary_stub = primary_stub
        self.client = client
        self.fallback_spec = fallback_spec

    async def ExecuteFunction(self, request):
        try:
            return await self.primary_stub.ExecuteFunction(request)
        except Exception as e:
            print(f"Primary server failed: {e}, trying fallback...")
            fallback_stub = self.client.get_stub(self.fallback_spec)
            return await fallback_stub.ExecuteFunction(request)


def remote(
    fallback: Union[None, str, List[str]] = None,
    resource_config: ServerlessResource = None,
    dependencies: List[str] = None,
):
    """
    Enhanced remote decorator that supports both traditional server specification
    and dynamic resource provisioning.

    Args:
        server_spec: Traditional server or pool name
        fallback: Fallback server or pool if primary fails
        resource_config: Configuration for dynamic resource provisioning
        dependencies: List of pip packages to install before executing the function
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            global_client = RemoteExecutionClient()
            _resource_manager = ResourceManager()

            # Determine if we're using dynamic provisioning or static server
            if resource_config:
                # Dynamic provisioning
                try:
                    # Get or create the resource
                    server_name = await _resource_manager.get_or_create_resource(resource_config)

                    # Check if server is already registered
                    if server_name not in global_client.servers:
                        # Get resource details
                        resource_id = None
                        for rid, details in _resource_manager._resources.items():
                            if details["server_name"] == server_name:
                                resource_id = rid
                                break

                        if not resource_id:
                            raise ValueError(
                                f"Resource details not found for {server_name}"
                            )

                        resource_details = _resource_manager._resources[resource_id]

                        # Register with the client
                        endpoint_url = resource_details["endpoint_url"]
                        print(
                            f"Registering RunPod endpoint: {server_name} at {endpoint_url}"
                        )
                        await global_client.add_runpod_server(
                            server_name, endpoint_url
                        )

                        # Ensure there's a pool for this resource
                        pool_name = f"pool_{resource_id}"
                        if pool_name not in global_client.pools:
                            global_client.create_pool(pool_name, [server_name])

                    # Use the server name for execution
                    effective_server_spec = server_name

                except Exception as e:
                    raise Exception(f"Failed to provision resource: {str(e)}")

            source = get_function_source(func)

            # Serialize arguments using cloudpickle instead of JSON
            serialized_args = [
                base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8") for arg in args
            ]
            serialized_kwargs = {
                k: base64.b64encode(cloudpickle.dumps(v)).decode("utf-8")
                for k, v in kwargs.items()
            }

            # Create request
            request_args = {
                "function_name": func.__name__,
                "function_code": source,
                "args": serialized_args,
                "kwargs": serialized_kwargs,
            }

            # Add dependencies if provided
            if dependencies:
                request_args["dependencies"] = dependencies

            request = remote_execution_pb2.FunctionRequest(**request_args)

            stub = global_client.get_stub(effective_server_spec, fallback)

            try:
                response = await stub.ExecuteFunction(request)
                if response.success:
                    # Deserialize result using cloudpickle instead of JSON
                    return cloudpickle.loads(base64.b64decode(response.result))
                else:
                    raise Exception(f"Remote execution failed: {response.error}")
            except Exception as e:
                raise Exception(f"All execution attempts failed: {str(e)}")

        return wrapper

    return decorator
