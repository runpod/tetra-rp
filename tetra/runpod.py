from typing import Dict, Any
from tetra.core.resources import ServerlessResourceInput


async def deploy_endpoint(config: Dict[str, Any], type: str) -> str:
    """
    Deploy a serverless endpoint on RunPod.

    Args:
        config: Configuration for the endpoint
        type: Type of deployment (e.g., "serverless", "sync")

    Returns:
        str: The endpoint URL
    """
    try:
        # Create endpoint using configuration
        new_endpoint = ServerlessResourceInput(**config)
        endpoint = await new_endpoint.deploy()
        return endpoint.url

    except Exception as e:
        print(f"Failed to deploy RunPod endpoint: {e}")
        raise


async def provision_resource(
    config: Dict[str, Any], resource_type: str
) -> Dict[str, Any]:
    """
    Provision a compute resource based on type and configuration.

    Args:
        config: Resource configuration
        resource_type: Type of resource to provision

    Returns:
        Dict: Resource details including endpoint URL and ID
    """
    if resource_type == "serverless":
        endpoint_url = await deploy_endpoint(config, resource_type)
        endpoint_id = endpoint_url.split("/")[-1]

        return {
            "endpoint_url": endpoint_url,
            "endpoint_id": endpoint_id,
            "type": resource_type,
        }
    else:
        raise ValueError(f"Unsupported resource type: {resource_type}")
