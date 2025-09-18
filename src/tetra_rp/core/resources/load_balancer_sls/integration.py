"""
LoadBalancerSls class execution handler.

This module provides the functionality to handle class decoration and execution
for LoadBalancerSls (Load Balancer) mode, following the same design patterns
as the existing execute_class module.
"""

import logging
from typing import List, Optional

from tetra_rp.core.resources import ServerlessResource
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

    This function follows the same synchronous pattern as create_remote_class but uses
    LoadBalancerSls for execution. The deployment will happen lazily when methods are called.

    Args:
        cls: The class to be wrapped for LoadBalancerSls execution
        resource_config: Configuration object specifying the serverless resource
        dependencies: List of pip packages to install
        system_dependencies: List of system packages to install
        extra: Additional parameters for execution

    Returns:
        Wrapped class that uses LoadBalancerSls for execution
    """
    extra = extra or {}

    # Follow the same deployment pattern as existing system
    log.info(f"Creating LoadBalancerSls class for {cls.__name__}")

    # For now, use the hardcoded URL as requested
    # TODO: Integrate with resource_config to get actual deployed endpoint URL
    endpoint_url = "https://9ttr6h4l3f17w3.api.runpod.ai"

    # Note: resource_config parameter will be used in future for actual deployment

    log.info(f"Using LoadBalancerSls endpoint: {endpoint_url}")

    # Create LoadBalancerSls instance following existing patterns
    runtime = LoadBalancerSls(endpoint_url=endpoint_url)

    # Return the wrapped class using LoadBalancerSls
    return runtime.remote_class(
        dependencies=dependencies, system_dependencies=system_dependencies
    )(cls)
