import orjson
import importlib
from typing import Dict
from pathlib import Path

from tetra_rp import get_logger
from tetra_rp.core.utils.json import normalize_for_json
from tetra_rp.core.utils.singleton import SingletonMixin

from .base import BaseResource, DeployableResource


log = get_logger("resource_manager")


RESOURCE_STATE_FILE = Path(".tetra_resources.json")


class ResourceManager(SingletonMixin):
    """Manages dynamic provisioning and tracking of remote resources."""

    _resources: Dict[str, BaseResource] = {}

    def __init__(self):
        if not self._resources:
            self._load_resources()

    def _load_resources(self) -> Dict[str, BaseResource]:
        """Load persisted resource information."""
        if RESOURCE_STATE_FILE.exists():
            try:
                with open(RESOURCE_STATE_FILE, "rb") as f:
                    resources_state = orjson.loads(f.read())
                    for k, v in resources_state.items():
                        class_name = k.split("_")[0]
                        module = importlib.import_module("tetra_rp.core.resources")
                        resource_class = getattr(module, class_name)
                        if resource_class:
                            # Produce the BaseResource object
                            self._resources[k] = resource_class(**v)

                    log.debug(f"Loaded saved resources from {RESOURCE_STATE_FILE}")

            except orjson.JSONDecodeError:
                log.error(f"Failed to load resources from {RESOURCE_STATE_FILE}")

    def _save_resources(self) -> None:
        """Persist state of resources to disk."""
        resources_state = {
            k: v.model_dump(exclude_none=True) for k, v in self._resources.items()
        }

        with open(RESOURCE_STATE_FILE, "w") as f:
            f.write(orjson.dumps(normalize_for_json(resources_state)).decode("utf-8"))
            log.debug(f"Saved resources in {RESOURCE_STATE_FILE}")

    def add_resource(self, uid: str, resource: BaseResource):
        """Add a resource to the manager."""
        self._resources[uid] = resource
        self._save_resources()

    async def get_or_create_resource(self, config: DeployableResource) -> BaseResource:
        """Get existing or create new resource based on config."""
        uid = config.resource_id
        if existing := self._resources.get(uid):
            log.debug(f"Resource {uid} exists, reusing.")
            return existing

        if deployed_resource := await config.deploy():
            self.add_resource(uid, deployed_resource)
            return deployed_resource
