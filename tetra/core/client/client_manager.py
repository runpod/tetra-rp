import base64
import cloudpickle
import time
from functools import wraps
from typing import Union, List, Dict
from .remote_execution import RemoteExecutionClient
from ..resources.serverless import ServerlessResource
from ..resources.resource_manager import ResourceManager
from ..utils.terminal import (
    Spinner, print_tetra, print_error, print_success, 
    print_warning, style_text, print_header, print_separator,
    print_box, print_step, TetraNotifier, show_summary, SmartProgress,
    print_info
)
from ... import remote_execution_pb2

# Keep track of servers already announced/connected to avoid redundant messages
_initialized_servers = set()
# Keep track of whether we've shown the welcome message
_shown_welcome = False
# Track operations for summary
_operations = []

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
            global _shown_welcome, _operations
            
            # Start timing the operation
            start_time = time.time()
            operation_record = {
                "operation": f"Execute {func.__name__}",
                "start_time": start_time,
                "success": False,
            }
            
            # Show welcome message only once per session
            if not _shown_welcome:
                TetraNotifier.welcome()
                _shown_welcome = True
            
            global_client = RemoteExecutionClient()
            _resource_manager = ResourceManager()
            effective_server_spec = None # Initialize with a default

            # Print execution step
            print_separator()
            print_step(1, f"Preparing {style_text(func.__name__, 'bright_yellow', 'bold')}", 
                    "Setting up resources and initializing execution environment")
            
            # Resource provisioning
            if resource_config:
                # Dynamic provisioning
                try:
                    # Show spinner while provisioning
                    with Spinner(f"Provisioning compute resources for {func.__name__}...", 
                                spinner_type="dots", 
                                icon="server",
                                color="bright_yellow"):
                        server_name = await _resource_manager.get_or_create_resource(resource_config)
                    
                    # Only show the detailed notification for newly created resources
                    if server_name not in _initialized_servers:
                        # Get resource details for display
                        resource_details = {}
                        for rid, details in _resource_manager._resources.items():
                            if details["server_name"] == server_name:
                                resource_details = {
                                    "gpu": details.get("gpuIds", "N/A"),
                                    "template": details.get("templateId", "N/A"),
                                    "endpoint": details.get("endpoint_url", "N/A")
                                }
                                break
                        
                        TetraNotifier.server_ready(server_name, resource_details)
                    else:
                        print_success(f"Using existing compute resource: {style_text(server_name, 'bright_green', 'bold')}")

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

                        # Register with the client ONLY if not already initialized
                        if server_name not in _initialized_servers:
                            endpoint_url = resource_details["endpoint_url"]
                            print_step(2, "Connecting to compute resource", 
                                    f"Establishing secure connection to {style_text(server_name, 'bright_cyan')}")
                            
                            with Spinner(f"Connecting to {server_name}...", 
                                       spinner_type="bounce", 
                                       icon="network",
                                       color="bright_blue"):
                                await global_client.add_runpod_server(
                                    server_name, endpoint_url
                                )
                            
                            print_success(f"Secure connection established to {style_text(server_name, 'bright_cyan', 'bold')}")
                            _initialized_servers.add(server_name)
                        else:
                            # If already initialized, just ensure it's in the client's list
                            if server_name not in global_client.servers:
                                 endpoint_url = resource_details["endpoint_url"]
                                 await global_client.add_runpod_server(server_name, endpoint_url)

                        # Ensure there's a pool for this resource
                        pool_name = f"pool_{resource_id}"
                        if pool_name not in global_client.pools:
                            global_client.create_pool(pool_name, [server_name])

                    effective_server_spec = server_name

                except Exception as e:
                    elapsed = time.time() - start_time
                    operation_record.update({
                        "success": False,
                        "result": "Failed to provision",
                        "duration": f"{elapsed:.1f}s", 
                        "error": str(e)
                    })
                    _operations.append(operation_record)
                    
                    print_error(f"Failed to provision resource: {str(e)}")
                    raise # Re-raise the exception after logging
            else:
                # Handle the case where no resource_config is provided
                # Allow for server_spec to be passed directly instead
                # First, check if this function has been called with a server_spec argument
                server_spec = kwargs.get('server_spec')
                if server_spec:
                    # Use the provided server_spec directly
                    effective_server_spec = server_spec
                    # Remove server_spec from kwargs to avoid passing it to the function
                    del kwargs['server_spec']
                    print_success(f"Using specified server: {style_text(server_spec, 'bright_green', 'bold')}")
                else:
                    # No explicit resource or server specification
                    elapsed = time.time() - start_time
                    operation_record.update({
                        "success": False,
                        "result": "No target specified",
                        "duration": f"{elapsed:.1f}s",
                    })
                    _operations.append(operation_record)
                    
                    print_error("Execution requires either resource_config or a server_spec parameter.")
                    raise ValueError("No execution target specified (resource_config or server_spec needed).")

            print_step(3, "Preparing function for remote execution", 
                     f"Serializing {style_text(func.__name__, 'bright_magenta', 'bold')} and its arguments")
            
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
                dependencies_str = ", ".join(dependencies)
                print_info(f"Including dependencies: {style_text(dependencies_str, 'bright_blue')}")
                request_args["dependencies"] = dependencies

            request = remote_execution_pb2.FunctionRequest(**request_args)

            try:
                print_step(4, "Establishing execution stub", 
                         f"Getting execution stub for {style_text(effective_server_spec, 'bright_cyan')}")
                
                with Spinner(f"Preparing communication channel...", 
                           spinner_type="arrows", 
                           icon="network",
                           color="bright_blue"):
                    stub = global_client.get_stub(effective_server_spec, fallback)
                    
            except ValueError as e:
                elapsed = time.time() - start_time
                operation_record.update({
                    "success": False,
                    "result": "Failed to get stub",
                    "duration": f"{elapsed:.1f}s",
                    "error": str(e)
                })
                _operations.append(operation_record)
                
                print_error(f"Failed to get execution stub: {e}")
                raise

            try:
                print_step(5, "Executing function remotely", 
                         f"Running {style_text(func.__name__, 'bright_magenta', 'bold')} on {style_text(effective_server_spec, 'bright_cyan', 'bold')}")
                
                # Notify about job submission
                TetraNotifier.job_submitted(func.__name__, effective_server_spec)
                
                # The actual execution happens in the stub, which now has its own spinner
                execution_start = time.time()
                response = await stub.ExecuteFunction(request)
                execution_time = time.time() - execution_start

                if response.success:
                    # Record successful operation
                    elapsed = time.time() - start_time
                    operation_record.update({
                        "success": True,
                        "result": "Success",
                        "duration": f"{elapsed:.1f}s",
                        "execution_time": execution_time
                    })
                    _operations.append(operation_record)
                    
                    # Show completion notification
                    TetraNotifier.job_completed(func.__name__, execution_time)
                    
                    # Deserialize result using cloudpickle instead of JSON
                    result = cloudpickle.loads(base64.b64decode(response.result))
                    
                    # Give a visual separator before showing results 
                    print_separator()
                    print_box(
                        f"Function: {style_text(func.__name__, 'bright_magenta', 'bold')}\n" +
                        f"Server: {style_text(effective_server_spec, 'bright_cyan')}\n" +
                        f"Execution time: {style_text(f'{execution_time:.2f}s', 'bright_yellow')}\n" +
                        f"Total time: {style_text(f'{elapsed:.2f}s', 'bright_yellow')}",
                        title="Execution Summary",
                        color="bright_green"
                    )
                    
                    return result
                else:
                    error_msg = f"Remote execution failed: {response.error}"
                    
                    # Record failed operation
                    elapsed = time.time() - start_time
                    operation_record.update({
                        "success": False,
                        "result": "Execution failed",
                        "duration": f"{elapsed:.1f}s",
                        "error": response.error,
                        "execution_time": execution_time
                    })
                    _operations.append(operation_record)
                    
                    print_error(error_msg)
                    raise Exception(error_msg)
            except Exception as e:
                # Catch potential communication errors or other exceptions during execution
                error_msg = f"Error during remote execution of {func.__name__}: {str(e)}"
                print_error(error_msg)
                
                # Attempt fallback if specified
                if fallback:
                    print_warning(f"Attempting fallback execution on {style_text(fallback, 'bright_yellow')}...")
                    try:
                        print_step(6, "Executing fallback", 
                                 f"Retrying {style_text(func.__name__, 'bright_magenta', 'bold')} on fallback {style_text(fallback, 'bright_yellow', 'bold')}")
                        
                        fallback_start = time.time()
                        fallback_stub = global_client.get_stub(fallback)
                        response = await fallback_stub.ExecuteFunction(request)
                        fallback_time = time.time() - fallback_start
                        
                        if response.success:
                            # Record successful fallback
                            elapsed = time.time() - start_time
                            operation_record.update({
                                "success": True,
                                "result": "Fallback succeeded",
                                "duration": f"{elapsed:.1f}s",
                                "execution_time": fallback_time,
                                "fallback_used": True
                            })
                            _operations.append(operation_record)
                            
                            print_success(f"Fallback execution of {style_text(func.__name__, 'bright_magenta', 'bold')} succeeded.")
                            TetraNotifier.job_completed(f"{func.__name__} (fallback)", fallback_time)
                            
                            # Give a visual separator before showing results 
                            print_separator()
                            print_box(
                                f"Function: {style_text(func.__name__, 'bright_magenta', 'bold')} (Fallback)\n" +
                                f"Server: {style_text(fallback, 'bright_yellow')}\n" +
                                f"Execution time: {style_text(f'{fallback_time:.2f}s', 'bright_yellow')}\n" +
                                f"Total time: {style_text(f'{elapsed:.2f}s', 'bright_yellow')}",
                                title="Fallback Execution Summary",
                                color="bright_green"
                            )
                            
                            return cloudpickle.loads(base64.b64decode(response.result))
                        else:
                            error_msg = f"Fallback execution failed: {response.error}"
                            
                            # Record failed fallback
                            elapsed = time.time() - start_time
                            operation_record.update({
                                "success": False,
                                "result": "All attempts failed",
                                "duration": f"{elapsed:.1f}s",
                                "error": f"Primary: {str(e)}, Fallback: {response.error}",
                                "fallback_used": True
                            })
                            _operations.append(operation_record)
                            
                            print_error(error_msg)
                            raise Exception(error_msg)
                    except Exception as fallback_e:
                         error_msg = f"Fallback execution also failed: {str(fallback_e)}"
                         
                         # Record failed fallback with exception
                         elapsed = time.time() - start_time
                         operation_record.update({
                             "success": False,
                             "result": "All attempts failed",
                             "duration": f"{elapsed:.1f}s",
                             "error": f"Primary: {str(e)}, Fallback exception: {str(fallback_e)}",
                             "fallback_used": True
                         })
                         _operations.append(operation_record)
                         
                         print_error(error_msg)
                         raise Exception(f"All execution attempts failed. Original error: {str(e)}. Fallback error: {str(fallback_e)}")
                else:
                    # Record the error without fallback
                    elapsed = time.time() - start_time
                    operation_record.update({
                        "success": False,
                        "result": "Failed",
                        "duration": f"{elapsed:.1f}s",
                        "error": str(e)
                    })
                    _operations.append(operation_record)
                    
                    raise Exception(f"All execution attempts failed: {str(e)}") # Re-raise if no fallback
            finally:
                # If we have accumulated operations, show a summary
                if len(_operations) >= 5:
                    show_summary(_operations)
                    # Reset the operations list to avoid showing redundant information
                    _operations = []

        return wrapper

    return decorator

def show_execution_history():
    """Display a summary of all remote executions performed in this session."""
    global _operations
    if _operations:
        show_summary(_operations)
        return len(_operations)
    return 0
