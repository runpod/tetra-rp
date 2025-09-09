"""
LoadBalancerSls class execution handler.

This module provides the functionality to handle class decoration and execution
for LoadBalancerSls (Load Balancer) mode, following the same design patterns
as the existing execute_class module.
"""

import logging
from typing import List, Optional

from tetra_rp.core.resources import ServerlessResource, ResourceManager
from .client import LoadBalancerSls

log = logging.getLogger(__name__)


def create_load_balancer_sls_class(
    cls,
    resource_config: ServerlessResource,
    dependencies: Optional[List[str]] = None,
    system_dependencies: Optional[List[str]] = None,
    extra: Optional[dict] = None,
):
    """
    Create a LoadBalancerSls-enabled class following existing deployment patterns.

    This function creates a wrapper that deploys the LoadBalancerSls endpoint dynamically
    using GraphQL and uses the deployed endpoint URL for LoadBalancerSls execution.

    Args:
        cls: The class to be wrapped for LoadBalancerSls execution
        resource_config: Configuration object specifying the serverless resource (with type="LB")
        dependencies: List of pip packages to install
        system_dependencies: List of system packages to install
        extra: Additional parameters for execution

    Returns:
        Wrapped class that uses LoadBalancerSls for execution
    """
    extra = extra or {}

    # Follow the same deployment pattern as existing system
    log.info(f"Creating LoadBalancerSls class for {cls.__name__}")

    # Verify this is a LoadBalancer resource
    if getattr(resource_config, 'type', None) != 'LB':
        raise ValueError(f"Expected LoadBalancer resource with type='LB', got type='{getattr(resource_config, 'type', None)}'")

    # Create a deployment wrapper that handles async deployment
    class LoadBalancerSlsClassWrapper:
        def __init__(self):
            self._deployed_endpoint_url = None
            self._deployment_lock = None
            
        async def _ensure_deployed(self):
            """Ensure the endpoint is deployed and get the URL."""
            if self._deployed_endpoint_url:
                return self._deployed_endpoint_url
                
            # Use ResourceManager to handle caching properly
            resource_manager = ResourceManager()
            deployed_resource = await resource_manager.get_or_deploy_resource(resource_config)

            # Construct the endpoint URL from the deployed endpoint ID
            # Format: https://ENDPOINT_ID.api.runpod.ai
            self._deployed_endpoint_url = f"https://{deployed_resource.id}.api.runpod.ai"
            
            log.info(f"LoadBalancerSls endpoint ready: {self._deployed_endpoint_url}")
            return self._deployed_endpoint_url
        
        def __call__(self, *args, **kwargs):
            """Create an instance that handles dynamic deployment."""
            return LoadBalancerSlsInstanceWrapper(
                cls, self, dependencies, system_dependencies, args, kwargs
            )
    
    return LoadBalancerSlsClassWrapper()


class LoadBalancerSlsInstanceWrapper:
    """Instance wrapper that handles async deployment and method routing."""
    
    def __init__(self, original_cls, class_wrapper, dependencies, system_dependencies, args, kwargs):
        self._original_cls = original_cls
        self._class_wrapper = class_wrapper
        self._dependencies = dependencies
        self._system_dependencies = system_dependencies
        self._args = args
        self._kwargs = kwargs
        self._runtime = None
        
    async def _get_runtime(self):
        """Get or create the LoadBalancerSls runtime with deployed endpoint."""
        if not self._runtime:
            endpoint_url = await self._class_wrapper._ensure_deployed()
            self._runtime = LoadBalancerSls(endpoint_url=endpoint_url)
            
            # Apply the remote_class decorator
            self._wrapped_class = self._runtime.remote_class(
                dependencies=self._dependencies, 
                system_dependencies=self._system_dependencies
            )(self._original_cls)
            
            # Create the actual instance
            self._instance = self._wrapped_class(*self._args, **self._kwargs)
            
        return self._runtime, self._instance
    
    def __getattr__(self, name):
        """Route method calls through the deployed runtime."""
        async def async_method_wrapper(*args, **kwargs):
            runtime, instance = await self._get_runtime()
            method = getattr(instance, name)
            return await method(*args, **kwargs)
        
        return async_method_wrapper
