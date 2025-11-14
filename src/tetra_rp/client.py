import os
import inspect
import logging
from functools import wraps
from typing import List, Optional

from .core.resources import ResourceManager, ServerlessResource
from .execute_class import create_remote_class
from .stubs import stub_resource

log = logging.getLogger(__name__)


def remote(
    resource_config: ServerlessResource,
    dependencies: Optional[List[str]] = None,
    system_dependencies: Optional[List[str]] = None,
    accelerate_downloads: bool = True,
    local: bool = False,
    **extra,
):
    """
    Decorator to enable dynamic resource provisioning and dependency management for serverless functions.

    This decorator allows a function to be executed in a remote serverless environment, with support for
    dynamic resource provisioning and installation of required dependencies. It can also bypass remote
    execution entirely for local testing.

    Supports both sync and async function definitions:
    - `def my_function(...)` - Regular synchronous function
    - `async def my_function(...)` - Asynchronous function

    In both cases, the decorated function returns an awaitable that must be called with `await`.

    Args:
        resource_config (ServerlessResource): Configuration object specifying the serverless resource
            to be provisioned or used. Not used when local=True.
        dependencies (List[str], optional): A list of pip package names to be installed in the remote
            environment before executing the function. Not used when local=True. Defaults to None.
        system_dependencies (List[str], optional): A list of system packages to be installed in the remote
            environment before executing the function. Not used when local=True. Defaults to None.
        accelerate_downloads (bool, optional): Enable download acceleration for dependencies and models.
            Only applies to remote execution. Defaults to True.
        local (bool, optional): Execute function/class locally instead of provisioning remote servers.
            Returns the unwrapped function/class for direct local execution. Users must ensure all required
            dependencies are already installed in their local environment. Defaults to False.
        extra (dict, optional): Additional parameters for the execution of the resource. Defaults to an empty dict.

    Returns:
        Callable: A decorator that wraps the target function, enabling remote execution with the specified
        resource configuration and dependencies, or returns the unwrapped function/class for local execution.

    Example:
    ```python
        # Async function (recommended style)
        @remote(
            resource_config=my_resource_config,
            dependencies=["torch>=2.0.0"],
        )
        async def gpu_task(data: dict) -> dict:
            import torch
            # GPU processing here
            return {"result": "processed"}

        # Sync function (also supported)
        @remote(
            resource_config=my_resource_config,
            dependencies=["pandas>=2.0.0"],
        )
        def cpu_task(data: dict) -> dict:
            import pandas as pd
            # CPU processing here
            return {"result": "processed"}

        # Local execution (testing/development)
        @remote(
            resource_config=my_resource_config,
            dependencies=["numpy", "pandas"],  # Only used for remote execution
            local=True,
        )
        async def my_test_function(data):
            # Runs locally - dependencies must be pre-installed
            pass
    ```
    """

    def decorator(func_or_class):
        if os.getenv("RUNPOD_POD_ID") or os.getenv("RUNPOD_ENDPOINT_ID"):
            # Worker mode when running on RunPod platform
            return func_or_class

        # Local execution mode - execute without provisioning remote servers
        if local:
            return func_or_class

        # Remote execution mode
        if inspect.isclass(func_or_class):
            # Handle class decoration
            return create_remote_class(
                func_or_class,
                resource_config,
                dependencies,
                system_dependencies,
                accelerate_downloads,
                extra,
            )
        else:
            # Handle function decoration
            @wraps(func_or_class)
            async def wrapper(*args, **kwargs):
                resource_manager = ResourceManager()
                remote_resource = await resource_manager.get_or_deploy_resource(
                    resource_config
                )

                stub = stub_resource(remote_resource, **extra)
                return await stub(
                    func_or_class,
                    dependencies,
                    system_dependencies,
                    accelerate_downloads,
                    *args,
                    **kwargs,
                )

            return wrapper

    return decorator
