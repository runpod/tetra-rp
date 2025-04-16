import base64
import cloudpickle
from functools import wraps
from typing import Union, List
from .remote_execution import RemoteExecutionClient
from ..resources.serverless import ServerlessResource
from ..resources.resource_manager import ResourceManager
from ... import remote_execution_pb2
import hashlib


# global in memory cache, TODO: use a more robust cache in future
_SERIALIZED_FUNCTION_CACHE = {} 


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
    
    # Return the function hash for cache key 
    source_hash = hashlib.sha256(function_source.encode("utf-8")).hexdigest()
    
    return function_source, source_hash


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

            source, src_hash = get_function_source(func)
            
            # check if the function is already cached
            if src_hash not in _SERIALIZED_FUNCTION_CACHE:
                # Cache the serialized function
                _SERIALIZED_FUNCTION_CACHE[src_hash] = source

            cached_src = _SERIALIZED_FUNCTION_CACHE[src_hash]
            
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
                "function_code": cached_src,
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
