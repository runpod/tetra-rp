import asyncio
import cloudpickle
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from ..exceptions import RunpodAPIKeyError
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
    _global_lock: Optional[asyncio.Lock] = None
    _lock_initialized = False
    _resources_initialized = False

    def __init__(self):
        # Ensure async locks are initialized properly for the singleton instance
        if not ResourceManager._lock_initialized:
            ResourceManager._global_lock = asyncio.Lock()
            ResourceManager._lock_initialized = True

        # Load resources immediately on initialization (only once)
        if not ResourceManager._resources_initialized:
            self._load_resources()
            ResourceManager._resources_initialized = True

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

    def _add_resource(self, uid: str, resource: DeployableResource):
        """Add a resource to the manager (protected method for internal use)."""
        self._resources[uid] = resource
        self._save_resources()

    def _remove_resource(self, uid: str):
        """Remove a resource from the manager (protected method for internal use)."""
        if uid not in self._resources:
            log.warning(f"Resource {uid} not found for removal")
            return

        del self._resources[uid]
        log.debug(f"Removed resource {uid}")

        self._save_resources()

    async def _deploy_with_error_context(
        self, config: DeployableResource
    ) -> DeployableResource:
        """Deploy resource with enhanced error context for RunpodAPIKeyError.

        Args:
            config: Resource configuration to deploy.

        Returns:
            Deployed resource instance.

        Raises:
            RunpodAPIKeyError: If deployment fails due to missing API key, with resource context.
        """
        try:
            return await config.deploy()
        except RunpodAPIKeyError as e:
            error_msg = f"Cannot deploy resource '{config.name}': {str(e)}"
            raise RunpodAPIKeyError(error_msg) from e

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
                if not existing.is_deployed():
                    log.warning(f"{existing} is no longer valid, redeploying.")
                    self._remove_resource(uid)
                    # Don't recursive call - deploy directly within the lock
                    deployed_resource = await self._deploy_with_error_context(config)
                    log.info(f"URL: {deployed_resource.url}")
                    self._add_resource(uid, deployed_resource)
                    return deployed_resource

                log.debug(f"{existing} exists, reusing.")
                log.info(f"URL: {existing.url}")
                return existing

            # No existing resource, deploy new one
            log.debug(f"Deploying new resource: {uid}")
            deployed_resource = await self._deploy_with_error_context(config)
            log.info(f"URL: {deployed_resource.url}")
            self._add_resource(uid, deployed_resource)
            return deployed_resource

    def list_all_resources(self) -> Dict[str, DeployableResource]:
        """List all tracked resources.

        Returns:
            Dictionary of resource_id -> DeployableResource
        """
        return self._resources.copy()

    def find_resources_by_name(self, name: str) -> List[Tuple[str, DeployableResource]]:
        """Find resources matching the given name.

        Args:
            name: The name to search for (exact match)

        Returns:
            List of (resource_id, resource) tuples matching the name
        """
        matches = []
        for uid, resource in self._resources.items():
            if hasattr(resource, "name") and resource.name == name:
                matches.append((uid, resource))
        return matches

    async def undeploy_resource(
        self, resource_id: str, resource_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Undeploy a resource and remove from tracking.

        This is the public interface for removing resources. It calls the resource's
        undeploy() method (polymorphic) and removes from tracking on success.

        Args:
            resource_id: The resource ID to undeploy
            resource_name: Optional human-readable name for error messages

        Returns:
            Dict with keys:
                - success: bool indicating if undeploy succeeded
                - name: resource name (if available)
                - endpoint_id: resource endpoint ID (if available)
                - message: status message
        """
        resource = self._resources.get(resource_id)

        if not resource:
            return {
                "success": False,
                "name": resource_name or "Unknown",
                "endpoint_id": "N/A",
                "message": f"Resource {resource_id} not found in tracking",
            }

        # Get resource metadata for response
        name = resource_name or getattr(resource, "name", "Unknown")
        endpoint_id = getattr(resource, "id", "N/A")

        try:
            # Call polymorphic undeploy method
            success = await resource.undeploy()

            if success:
                # Remove from tracking on successful undeploy
                self._remove_resource(resource_id)
                return {
                    "success": True,
                    "name": name,
                    "endpoint_id": endpoint_id,
                    "message": f"Successfully undeployed '{name}' ({endpoint_id})",
                }
            else:
                return {
                    "success": False,
                    "name": name,
                    "endpoint_id": endpoint_id,
                    "message": f"Failed to undeploy '{name}' ({endpoint_id})",
                }

        except NotImplementedError as e:
            # Resource type doesn't support undeploy yet
            return {
                "success": False,
                "name": name,
                "endpoint_id": endpoint_id,
                "message": f"Cannot undeploy '{name}': {str(e)}",
            }
        except Exception as e:
            # Unexpected error during undeploy
            return {
                "success": False,
                "name": name,
                "endpoint_id": endpoint_id,
                "message": f"Error undeploying '{name}': {str(e)}",
            }
