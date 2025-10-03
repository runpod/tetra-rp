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
    hf_models_to_cache: Optional[List[str]] = None,
    mode: str = "dev",
    **extra,
):
    """
    Decorator to enable dynamic resource provisioning and dependency management for serverless functions.

    This decorator allows a function to be executed in a remote serverless environment, with support for
    dynamic resource provisioning and installation of required dependencies.

    Args:
        resource_config (ServerlessResource): Configuration object specifying the serverless resource
            to be provisioned or used.
        dependencies (List[str], optional): A list of pip package names to be installed in the remote
            environment before executing the function. Defaults to None.
        system_dependencies (List[str], optional): A list of system packages to be installed in the remote
            environment before executing the function. Defaults to None.
        accelerate_downloads (bool, optional): Enable download acceleration for dependencies and models.
            Defaults to True.
        hf_models_to_cache (List[str], optional): List of HuggingFace model IDs to pre-cache using
            download acceleration. Defaults to None.
        mode (str, optional): Execution mode - "dev" (send code via HTTP) or "prod" (bake code into Docker image).
            Defaults to "dev".
        extra (dict, optional): Additional parameters for the execution of the resource. Defaults to an empty dict.

    Returns:
        Callable: A decorator that wraps the target function, enabling remote execution with the
        specified resource configuration and dependencies.

    Example:
    ```python
        @remote(
            resource_config=my_resource_config,
            dependencies=["numpy", "pandas"],
            accelerate_downloads=True,
            hf_models_to_cache=["gpt2", "bert-base-uncased"],
            mode="prod"
        )
        async def my_function(data):
            # Function logic here
            pass
    ```
    """

    def decorator(func_or_class):
        # If prod mode, trigger automatic build and deploy
        if mode == "prod":
            from .build import build_production_image

            build_production_image(
                func_or_class,
                resource_config,
                dependencies,
                system_dependencies,
            )
        if inspect.isclass(func_or_class):
            # Handle class decoration
            return create_remote_class(
                func_or_class,
                resource_config,
                dependencies,
                system_dependencies,
                accelerate_downloads,
                hf_models_to_cache,
                extra,
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
                    func_or_class,
                    dependencies,
                    system_dependencies,
                    accelerate_downloads,
                    hf_models_to_cache,
                    *args,
                    **kwargs,
                )

            return wrapper

    return decorator
