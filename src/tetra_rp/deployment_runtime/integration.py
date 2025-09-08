"""
DeploymentRuntime class execution handler.

This module provides the functionality to handle class decoration and execution
for DeploymentRuntime (Load Balancer) mode, following the same design patterns
as the existing execute_class module.
"""

import asyncio
import logging
from typing import List, Optional

from ..core.resources import ResourceManager, ServerlessResource
from .client import DeploymentRuntime

log = logging.getLogger(__name__)


def create_deployment_runtime_class(
    cls,
    resource_config: ServerlessResource,
    dependencies: Optional[List[str]] = None,
    system_dependencies: Optional[List[str]] = None,
    extra: Optional[dict] = None,
):
    """
    Create a DeploymentRuntime-enabled class following existing deployment patterns.

    This function follows the same lazy deployment pattern as the existing serverless system.
    The actual deployment and URL construction happens when the class methods are first called.

    Args:
        cls: The class to be wrapped for DeploymentRuntime execution
        resource_config: Configuration object specifying the serverless resource
        dependencies: List of pip packages to install
        system_dependencies: List of system packages to install
        extra: Additional parameters for execution

    Returns:
        Wrapped class that uses DeploymentRuntime for execution
    """
    extra = extra or {}

    # Follow the same lazy deployment pattern as existing system
    log.info(f"Creating DeploymentRuntime class for {cls.__name__}")

    class DeploymentRuntimeWrapper:
        def __init__(self):
            self._runtime = None
            self._wrapped_instance = None
            self._deployment_lock = asyncio.Lock()

        def __call__(self, *args, **kwargs):
            """Make the wrapper callable like a class constructor."""
            # Return a new instance wrapper that handles method calls
            return DeploymentRuntimeInstanceWrapper(
                self,
                cls,
                resource_config,
                dependencies,
                system_dependencies,
                args,
                kwargs,
            )

        async def _ensure_deployed(self):
            """Lazy deployment following existing serverless pattern."""
            if self._runtime is not None:
                return self._runtime

            async with self._deployment_lock:
                if self._runtime is not None:
                    return self._runtime

                # Step 1: Configure and deploy the serverless resource as LB type using ResourceManager
                log.info(f"Deploying serverless resource: {resource_config.name}")
                resource_config.type = "LB"  # Set Load Balancer type

                # Use ResourceManager for proper caching like existing system
                resource_manager = ResourceManager()
                deployed_resource = await resource_manager.get_or_deploy_resource(
                    resource_config
                )

                # Step 2: Extract endpoint ID from deployed resource
                if not deployed_resource.id:
                    raise ValueError("Deployment failed: no endpoint ID returned")

                # Step 3: Construct DeploymentRuntime URL using discovered pattern
                endpoint_url = f"https://{deployed_resource.id}.api.runpod.ai"
                log.info(f"Using DeploymentRuntime endpoint: {endpoint_url}")

                # Create and cache DeploymentRuntime instance
                self._runtime = DeploymentRuntime(endpoint_url=endpoint_url)

            return self._runtime

    class DeploymentRuntimeInstanceWrapper:
        def __init__(
            self,
            wrapper,
            cls,
            resource_config,
            dependencies,
            system_dependencies,
            args,
            kwargs,
        ):
            self._wrapper = wrapper
            self._cls = cls
            self._resource_config = resource_config
            self._dependencies = dependencies
            self._system_dependencies = system_dependencies
            self._args = args
            self._kwargs = kwargs

        def __getattr__(self, name):
            """Proxy attribute access to ensure deployment happens before method calls."""

            async def method_wrapper(*method_args, **method_kwargs):
                runtime = await self._wrapper._ensure_deployed()
                wrapped_cls = runtime.remote_class(
                    dependencies=self._dependencies,
                    system_dependencies=self._system_dependencies,
                )(self._cls)
                instance = wrapped_cls(*self._args, **self._kwargs)
                return await getattr(instance, name)(*method_args, **method_kwargs)

            return method_wrapper

    return DeploymentRuntimeWrapper()
