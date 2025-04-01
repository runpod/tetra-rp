import json
from typing import Any, Dict
from pathlib import Path
from .core.utils.json import normalize_for_json
from .core.utils.singleton import SingletonMixin
from .core.resources import DeployableResource

RESOURCE_STATE_FILE = Path(".tetra_resources.json")


class ResourceManager(SingletonMixin):
    """Manages dynamic provisioning and tracking of remote resources."""

    def __init__(self):
        self._resources = self._load_resources()
        self._client = None

    def _load_resources(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted resource information."""
        if RESOURCE_STATE_FILE.exists():
            try:
                with open(RESOURCE_STATE_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_resources(self) -> None:
        """Persist resource information to disk."""
        with open(RESOURCE_STATE_FILE, "w") as f:
            json.dump(normalize_for_json(self._resources), f, indent=2)

    async def get_or_create_resource(self, config: DeployableResource) -> str:
        """Get existing or create new resource based on config."""
        resource_id = config.resource_id

        # Check if resource already exists
        if resource_id in self._resources:
            print(f"Resource {resource_id} already exists, reusing.")
            return self._resources[resource_id]["server_name"]

        # Deploy new resource based on type
        endpoint = await config.deploy()

        # Create a server name for this resource
        server_name = f"server_{resource_id}"

        # Store resource info
        self._resources[resource_id] = {
            "config": config.model_dump(exclude_none=True),
            "endpoint_url": endpoint.url,
            "endpoint_id": endpoint.id,
            "server_name": server_name,
        }

        self._save_resources()
        return server_name
