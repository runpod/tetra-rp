import os
import asyncio
import runpod
from typing import Dict, Any, Optional


async def deploy_endpoint(config: Dict[str, Any], type: str) -> str:
    """
    Deploy a serverless endpoint on RunPod.

    Args:
        config: Configuration for the endpoint
        type: Type of deployment (e.g., "serverless", "sync")

    Returns:
        str: The endpoint URL
    """
    # Set API key from config or environment
    api_key = config.get("api_key", os.environ.get("RUNPOD_API_KEY"))
    if not api_key:
        raise ValueError("RunPod API key not provided in config or environment")

    runpod.api_key = api_key

    try:
        # Create endpoint using configuration
        new_endpoint = runpod.create_endpoint(
            name=config.get("name", f"tetra-endpoint-{type}"),
            template_id=config.get("template_id", "ib4coc7w60"),
            gpu_ids=config.get("gpu_ids", "AMPERE_16"),
            workers_min=config.get("workers_min", 0),
            workers_max=config.get("workers_max", 1),
        )

        endpoint_id = new_endpoint.get("id")
        if not endpoint_id:
            raise ValueError("Failed to get endpoint ID from RunPod response")

        endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        print(f"Endpoint created: {endpoint_url}")

        return endpoint_url
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
