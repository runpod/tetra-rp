import cloudpickle
import logging
from typing import Dict
from pathlib import Path

from ..utils.singleton import SingletonMixin

from .base import DeployableResource


log = logging.getLogger(__name__)

# File to persist state of resources
RESOURCE_STATE_FILE = Path(".tetra_resources.pkl")


class ResourceManager(SingletonMixin):
    """Manages dynamic provisioning and tracking of remote resources."""

    _resources: Dict[str, DeployableResource] = {}

    def __init__(self):
        if not self._resources:
            self._load_resources()

    def _load_resources(self) -> Dict[str, DeployableResource]:
        """Load persisted resource information using cloudpickle."""
        if RESOURCE_STATE_FILE.exists():
            try:
                with open(RESOURCE_STATE_FILE, "rb") as f:
                    self._resources = cloudpickle.load(f)
                    log.debug(f"Loaded saved resources from {RESOURCE_STATE_FILE}")
            except Exception as e:
                log.error(f"Failed to load resources from {RESOURCE_STATE_FILE}: {e}")
        return self._resources

    def _save_resources(self) -> None:
        """Persist state of resources to disk using cloudpickle."""
        with open(RESOURCE_STATE_FILE, "wb") as f:
            cloudpickle.dump(self._resources, f)
        log.debug(f"Saved resources in {RESOURCE_STATE_FILE}")

    def add_resource(self, uid: str, resource: DeployableResource):
        """Add a resource to the manager."""
        self._resources[uid] = resource
        self._save_resources()

    # function to check if resource still exists remotely, else remove it
    def remove_resource(self, uid: str):
        """Remove a resource from the manager."""
        if uid not in self._resources:
            log.warning(f"Resource {uid} not found for removal")
            return

        del self._resources[uid]
        log.debug(f"Removed resource {uid}")

        self._save_resources()

    async def get_or_deploy_resource(
        self, config: DeployableResource
    ) -> DeployableResource:
        """Get existing or create new resource based on config."""
        uid = config.resource_id
        if existing := self._resources.get(uid):
            if not existing.is_deployed():
                log.warning(f"{existing} is no longer valid, redeploying.")
                self.remove_resource(uid)
                return await self.get_or_deploy_resource(config)

            log.debug(f"{existing} exists, reusing.")
            log.info(f"URL: {existing.url}")
            return existing

        if deployed_resource := await config.deploy():
            log.info(f"URL: {deployed_resource.url}")
            self.add_resource(uid, deployed_resource)
            return deployed_resource

        raise RuntimeError(f"Deployment failed for resource {uid}")
