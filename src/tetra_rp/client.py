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
    **extra,
):
    """
    Decorator to enable dynamic resource provisioning and dependency management for serverless functions.

    This decorator allows a function to be executed in a remote serverless environment, with support for
    dynamic resource provisioning and installation of required dependencies.

        resource_config (ServerlessResource): Configuration object specifying the serverless resource
            to be provisioned or used.
        dependencies (List[str], optional): A list of pip package names to be installed in the remote
            environment before executing the function. Defaults to None.
        extra (dict, optional): Additional parameters for the execution of the resource. Defaults to an empty dict.

    Returns:
        Callable: A decorator that wraps the target function, enabling remote execution with the
        specified resource configuration and dependencies.

    Example:
    ```python
        @remote(
            resource_config=my_resource_config,
            dependencies=["numpy", "pandas"],
            sync=True  # Optional, to run synchronously
        )
        async def my_function(data):
            # Function logic here
            pass
    ```
    """

    def decorator(func_or_class):
        if inspect.isclass(func_or_class):
            # Handle class decoration
            return create_remote_class(
                func_or_class, resource_config, dependencies, system_dependencies, extra
            )
        else:
            # Handle function decoration (unchanged)
            @wraps(func_or_class)
            async def wrapper(*args, **kwargs):
                resource_manager = ResourceManager()
                remote_resource = await resource_manager.get_or_deploy_resource(
                    resource_config
                )

                stub = stub_resource(remote_resource, **extra)
                return await stub(
                    func_or_class, dependencies, system_dependencies, *args, **kwargs
                )

            return wrapper

    return decorator
