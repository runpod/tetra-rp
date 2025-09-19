import asyncio
import cloudpickle
import logging
from typing import Dict, Optional
from pathlib import Path

from ..utils.singleton import SingletonMixin
from ..utils.file_lock import file_lock, FileLockError

from .base import DeployableResource


log = logging.getLogger(__name__)

# File to persist state of resources
RESOURCE_STATE_FILE = Path(".tetra_resources.pkl")


class ResourceManager(SingletonMixin):
    """Manages dynamic provisioning and tracking of remote resources."""

    # Class variables shared across all instances (singleton)
    _resources: Dict[str, DeployableResource] = {}
    _deployment_locks: Dict[str, asyncio.Lock] = {}
    _global_lock: Optional[asyncio.Lock] = None  # Will be initialized lazily
    _lock_initialized = False

    def __init__(self):
        # Ensure async locks are initialized properly for the singleton instance
        if not ResourceManager._lock_initialized:
            ResourceManager._global_lock = asyncio.Lock()
            ResourceManager._lock_initialized = True

        if not self._resources:
            self._load_resources()

    def _load_resources(self) -> Dict[str, DeployableResource]:
        """Load persisted resource information using cross-platform file locking."""
        if RESOURCE_STATE_FILE.exists():
            try:
                with open(RESOURCE_STATE_FILE, "rb") as f:
                    # Acquire shared lock for reading (cross-platform)
                    with file_lock(f, exclusive=False):
                        self._resources = cloudpickle.load(f)
                        log.debug(f"Loaded saved resources from {RESOURCE_STATE_FILE}")
            except (FileLockError, Exception) as e:
                log.error(f"Failed to load resources from {RESOURCE_STATE_FILE}: {e}")
        return self._resources

    def _save_resources(self) -> None:
        """Persist state of resources to disk using cross-platform file locking."""
        try:
            with open(RESOURCE_STATE_FILE, "wb") as f:
                # Acquire exclusive lock for writing (cross-platform)
                with file_lock(f, exclusive=True):
                    cloudpickle.dump(self._resources, f)
                    f.flush()  # Ensure data is written to disk
                    log.debug(f"Saved resources in {RESOURCE_STATE_FILE}")
        except (FileLockError, Exception) as e:
            log.error(f"Failed to save resources to {RESOURCE_STATE_FILE}: {e}")
            raise

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
        """Get existing or create new resource based on config.

        Thread-safe implementation that prevents concurrent deployments
        of the same resource configuration.
        """
        uid = config.resource_id

        # Ensure global lock is initialized (should be done in __init__)
        assert ResourceManager._global_lock is not None, "Global lock not initialized"

        # Get or create a per-resource lock
        async with ResourceManager._global_lock:
            if uid not in ResourceManager._deployment_locks:
                ResourceManager._deployment_locks[uid] = asyncio.Lock()
            resource_lock = ResourceManager._deployment_locks[uid]

        # Acquire per-resource lock for this specific configuration
        async with resource_lock:
            # Double-check pattern: check again inside the lock
            if existing := self._resources.get(uid):
                # if the old resource isn't actually deployed, then we can just deploy the new one
                if not existing.is_deployed():
                    log.warning(f"{existing} is no longer valid, redeploying.")
                    self.remove_resource(uid)
                    # Don't recursive call - deploy directly within the lock
                    deployed_resource = await config.deploy()
                    log.info(f"URL: {deployed_resource.url}")
                    self.add_resource(uid, deployed_resource)
                    return deployed_resource

                # if the old resource is actually deployed, then we need to update it
                if existing.resource_hash != config.resource_hash:
                    log.info(f"change in resource configuration detected, updating resource.")
                    for field in existing.__class__._hashed_fields:
                        existing_value, new_value = getattr(existing, field), getattr(config, field)
                        if existing_value != new_value:
                            log.debug(f"field: {field}, existing value: {getattr(existing, field)}, new value: {getattr(config, field)}")
                            config.fields_to_update.add(field)

                    # there are some fields that should be stored in pickled state and should be loaded back to the new obj
                    # these are used to make updates to platform endpoints/resources
                    # TODO: clean this up
                    await config.sync_config_with_deployed_resource(existing)
                    deployed_resource = await config.update()
                    self.remove_resource(uid)
                    self.add_resource(uid, deployed_resource)
                    return deployed_resource

                # otherwise, nothing has changed and we just return what we already have
                log.debug(f"{existing} exists, reusing.")
                log.info(f"URL: {existing.url}")
                return existing

            # No existing resource, deploy new one
            log.debug(f"Deploying new resource: {uid}")
            deployed_resource = await config.deploy()
            log.info(f"URL: {deployed_resource.url}")
            self.add_resource(uid, deployed_resource)
            return deployed_resource
