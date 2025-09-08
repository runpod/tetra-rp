import inspect
import logging
from functools import wraps
from typing import List, Optional

from .core.resources import ResourceManager, ServerlessResource, LoadBalancerSlsResource
from .execute_class import create_remote_class
from .core.resources.load_balancer_sls.integration import create_load_balancer_sls_class
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
            to be provisioned or used. Set resource_config.type="LB" for LoadBalancerSls mode.
        dependencies (List[str], optional): A list of pip package names to be installed in the remote
            environment before executing the function. Defaults to None.
        system_dependencies (List[str], optional): A list of system packages to install. Defaults to None.
        extra (dict, optional): Additional parameters for the execution of the resource. Defaults to an empty dict.

    Returns:
        Callable: A decorator that wraps the target function, enabling remote execution with the
        specified resource configuration and dependencies.

    Example:
    ```python
        # Traditional serverless execution
        @remote(
            resource_config=my_resource_config,
            dependencies=["numpy", "pandas"],
            sync=True  # Optional, to run synchronously
        )
        async def my_function(data):
            # Function logic here
            pass

        # LoadBalancerSls execution (Load Balancer mode)
        @remote(
            resource_config=my_resource_config,
            type="LB",
            dependencies=["torch", "transformers"]
        )
        class MLModel:
            @endpoint(methods=['POST'])
            def predict(self, data):
                return result
    ```
    """

    def decorator(func_or_class):
        if inspect.isclass(func_or_class):
            # Handle class decoration
            if isinstance(resource_config, LoadBalancerSlsResource):
                # Use LoadBalancerSls (Load Balancer) mode
                log.info(
                    f"Using LoadBalancerSls mode for class {func_or_class.__name__}"
                )
                return create_load_balancer_sls_class(
                    func_or_class,
                    resource_config,
                    dependencies,
                    system_dependencies,
                    extra,
                )
            else:
                # Use traditional serverless execution
                return create_remote_class(
                    func_or_class,
                    resource_config,
                    dependencies,
                    system_dependencies,
                    extra,
                )
        else:
            # Handle function decoration (unchanged)
            if isinstance(resource_config, LoadBalancerSlsResource):
                raise ValueError(
                    "LoadBalancerSlsResource can only be used with classes, not functions"
                )

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
