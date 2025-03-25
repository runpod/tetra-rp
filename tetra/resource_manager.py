import json

from typing import Any, Dict
import hashlib
import os

from .runpod import deploy_endpoint


RESOURCE_STATE_FILE = os.path.expanduser("~/.tetra_resources.json")


class ResourceManager:
    """Manages dynamic provisioning and tracking of remote resources."""

    def __init__(self):
        self._resources = self._load_resources()
        self._client = None

    def _load_resources(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted resource information."""
        if os.path.exists(RESOURCE_STATE_FILE):
            try:
                with open(RESOURCE_STATE_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_resources(self) -> None:
        """Persist resource information to disk."""
        with open(RESOURCE_STATE_FILE, "w") as f:
            json.dump(self._resources, f, indent=2)

    def _generate_resource_id(self, config: Dict[str, Any], resource_type: str) -> str:
        """Generate a unique resource ID based on configuration."""
        config_str = json.dumps(config, sort_keys=True)
        hash_obj = hashlib.md5(f"{config_str}:{resource_type}".encode())
        return f"{resource_type}_{hash_obj.hexdigest()[:8]}"

    async def get_or_create_resource(
        self, config: Dict[str, Any], resource_type: str
    ) -> str:
        """Get existing or create new resource based on config."""
        resource_id = self._generate_resource_id(config, resource_type)

        # Check if resource already exists
        if resource_id in self._resources:
            print(f"Resource {resource_id} already exists, reusing.")
            return self._resources[resource_id]["server_name"]

        # Deploy new resource based on type
        if resource_type == "serverless":
            endpoint_url = await self._deploy_serverless(resource_id, config)

            # Extract endpoint details
            # Assuming the endpoint URL is like: https://api.runpod.ai/v2/{endpoint_id}/
            endpoint_id = endpoint_url.split("/")[-2]

            # Create a server name for this resource
            server_name = f"server_{resource_id}"

            # Store resource info
            self._resources[resource_id] = {
                "type": resource_type,
                "config": config,
                "endpoint_url": endpoint_url,
                "endpoint_id": endpoint_id,
                "server_name": server_name,
            }

            self._save_resources()
            return server_name
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")

    async def _deploy_serverless(self, resource_id: str, config: Dict[str, Any]) -> str:
        """Deploy a serverless endpoint using the existing deploy_endpoint function."""
        # We're using the existing deployment function
        endpoint_url = await deploy_endpoint(config, "serverless")
        return endpoint_url
