"""Runtime service registry for cross-endpoint function routing."""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from tetra_rp.core.resources.serverless import ServerlessResource

from .config import DEFAULT_CACHE_TTL
from .manifest_client import ManifestClient, ManifestServiceUnavailableError
from .models import Manifest

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Service discovery and routing for cross-endpoint function calls.

    Loads manifest to map functions to resource configs, queries mothership
    directory for endpoint URLs, and determines if function calls are local
    or remote.
    """

    def __init__(
        self,
        manifest_path: Optional[Path] = None,
        directory_client: Optional[ManifestClient] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """Initialize service registry.

        Args:
            manifest_path: Path to flash_manifest.json. Defaults to
                FLASH_MANIFEST_PATH env var or auto-detection.
            directory_client: Manifest service client for mothership API. If None, creates one
                from FLASH_MOTHERSHIP_ID env var.
            cache_ttl: Directory cache lifetime in seconds (default: 300).

        Environment Variables (for local vs remote detection):
            FLASH_RESOURCE_NAME: Resource config name for this endpoint (child endpoints only).
                Identifies which resource config this endpoint represents in the manifest.
            RUNPOD_ENDPOINT_ID: Endpoint ID (used as fallback for mothership identification).

        Raises:
            FileNotFoundError: If manifest_path doesn't exist.
            ValueError: If required env vars missing for directory_client.
        """
        self.cache_ttl = cache_ttl
        self._directory: Dict[str, str] = {}
        self._directory_loaded_at = 0.0
        self._manifest: Manifest = Manifest(
            version="1.0",
            generated_at="",
            project_name="",
            function_registry={},
            resources={},
        )
        self._directory_lock = asyncio.Lock()

        # Load manifest
        self._load_manifest(manifest_path)

        # Initialize manifest client
        if directory_client is None:
            mothership_id = os.getenv("FLASH_MOTHERSHIP_ID")
            if mothership_id:
                try:
                    directory_client = ManifestClient()
                except ValueError as e:
                    logger.warning(f"Failed to initialize manifest client: {e}")
                    directory_client = None
            else:
                logger.debug("FLASH_MOTHERSHIP_ID not set, directory unavailable")
                directory_client = None

        self._directory_client = directory_client
        # Child endpoints use FLASH_RESOURCE_NAME to identify which resource config they represent
        # Mothership doesn't have FLASH_RESOURCE_NAME, so falls back to RUNPOD_ENDPOINT_ID
        self._current_endpoint = os.getenv("FLASH_RESOURCE_NAME") or os.getenv(
            "RUNPOD_ENDPOINT_ID"
        )

    def _load_manifest(self, manifest_path: Optional[Path]) -> None:
        """Load flash_manifest.json.

        Args:
            manifest_path: Explicit path to manifest. Tries env var and
                auto-detection if not provided.

        Raises:
            FileNotFoundError: If manifest not found.
        """
        paths_to_try = []

        # Explicit path
        if manifest_path:
            paths_to_try.append(manifest_path)

        # Environment variable
        env_path = os.getenv("FLASH_MANIFEST_PATH")
        if env_path:
            paths_to_try.append(Path(env_path))

        # Auto-detection: same directory as this file, or cwd
        paths_to_try.extend(
            [
                Path(__file__).parent.parent.parent / "flash_manifest.json",
                Path.cwd() / "flash_manifest.json",
            ]
        )

        # Try each path
        for path in paths_to_try:
            if path and path.exists():
                try:
                    with open(path) as f:
                        manifest_dict = json.load(f)
                    self._manifest = Manifest.from_dict(manifest_dict)
                    logger.debug(f"Manifest loaded from {path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load manifest from {path}: {e}")
                    continue

        # No manifest found - log warning but don't fail
        logger.warning(
            "flash_manifest.json not found. Cross-endpoint routing disabled. "
            "Manifest is required for routing functions between endpoints."
        )
        self._manifest = Manifest(
            version="1.0",
            generated_at="",
            project_name="",
            function_registry={},
            resources={},
        )

    async def _ensure_directory_loaded(self) -> None:
        """Load directory from mothership if cache expired or not loaded."""
        async with self._directory_lock:
            now = time.time()
            cache_age = now - self._directory_loaded_at

            if cache_age > self.cache_ttl:
                if self._directory_client is None:
                    logger.debug("Directory client not available, skipping refresh")
                    return

                try:
                    self._directory = await self._directory_client.get_directory()
                    self._directory_loaded_at = now
                    logger.debug(
                        f"Directory loaded: {len(self._directory)} endpoints, "
                        f"cache TTL {self.cache_ttl}s"
                    )
                except ManifestServiceUnavailableError as e:
                    logger.warning(
                        f"Failed to load manifest directory: {e}. "
                        f"Cross-endpoint routing unavailable."
                    )
                    self._directory = {}

    def get_endpoint_for_function(self, function_name: str) -> Optional[str]:
        """Get endpoint URL for a function.

        Determines if function is local (same endpoint) or remote (different
        endpoint), returning None for local and URL for remote.

        Args:
            function_name: Name of the function to route.

        Returns:
            Endpoint URL if function is remote, None if local.

        Raises:
            ValueError: If function not in manifest.
        """
        function_registry = self._manifest.function_registry

        if function_name not in function_registry:
            raise ValueError(
                f"Function '{function_name}' not found in manifest. "
                f"Available functions: {list(function_registry.keys())}"
            )

        resource_config_name = function_registry[function_name]

        # Check if this is the current endpoint (local)
        if resource_config_name == self._current_endpoint:
            return None

        # Check directory for remote endpoint URL
        endpoint_url = self._directory.get(resource_config_name)
        if not endpoint_url:
            logger.debug(
                f"Endpoint URL for '{resource_config_name}' not in directory. "
                f"Directory has: {list(self._directory.keys())}"
            )

        return endpoint_url

    def get_resource_for_function(
        self, function_name: str
    ) -> Optional[ServerlessResource]:
        """Get ServerlessResource for a function.

        Creates a ServerlessResource with the correct endpoint ID if the function
        is remote, returns None if local.

        Args:
            function_name: Name of the function to route.

        Returns:
            ServerlessResource with ID set if function is remote
            None if function runs on current endpoint

        Raises:
            ValueError: If function not in manifest.
        """
        endpoint_url = self.get_endpoint_for_function(function_name)

        if endpoint_url is None:
            return None  # Local function

        # Extract endpoint ID from URL (format: https://api.runpod.io/v2/{endpoint_id})
        try:
            parsed = urlparse(endpoint_url)
            # Get the last path component (the endpoint ID)
            path_parts = parsed.path.rstrip("/").split("/")
            endpoint_id = path_parts[-1] if path_parts else ""

            if not endpoint_id:
                raise ValueError(
                    f"Invalid endpoint URL format: {endpoint_url} - no endpoint ID found"
                )
        except Exception as e:
            raise ValueError(
                f"Failed to parse endpoint URL '{endpoint_url}': {e}"
            ) from e

        # Create and return ServerlessResource
        resource = ServerlessResource(name=f"remote_{function_name}")
        resource.id = endpoint_id

        return resource

    def is_local_function(self, function_name: str) -> bool:
        """Check if function executes on current endpoint.

        Args:
            function_name: Name of the function.

        Returns:
            True if function is local, False if remote or not found.
        """
        try:
            endpoint_url = self.get_endpoint_for_function(function_name)
            return endpoint_url is None
        except ValueError:
            # Function not in manifest, assume local (will execute and fail)
            return True

    def get_current_endpoint_id(self) -> Optional[str]:
        """Get ID of current endpoint from environment.

        Returns:
            Endpoint ID from RUNPOD_ENDPOINT_ID, or None if not set.
        """
        return self._current_endpoint

    def refresh_directory(self) -> None:
        """Force refresh directory from mothership on next access."""
        self._directory_loaded_at = 0

    def get_manifest(self) -> Manifest:
        """Get loaded manifest.

        Returns:
            Loaded Manifest object.
        """
        return self._manifest

    def get_all_resources(self) -> Dict[str, Dict]:
        """Get all resource configs from manifest.

        Returns:
            Dictionary of resource configs as dictionaries.
        """
        from dataclasses import asdict

        return {
            name: asdict(config) for name, config in self._manifest.resources.items()
        }

    def get_resource_functions(self, resource_name: str) -> list:
        """Get list of functions for a resource.

        Args:
            resource_name: Name of the resource config.

        Returns:
            List of function metadata dictionaries.
        """
        resource = self._manifest.resources.get(resource_name)
        if not resource:
            return []
        from dataclasses import asdict

        return [asdict(func) for func in resource.functions]
