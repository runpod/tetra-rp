"""HTTP client for State Manager API to persist and reconcile manifests."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from tetra_rp.core.api.runpod import RunpodGraphQLClient

try:
    import httpx
except ImportError:
    httpx = None

from .config import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT
from .exceptions import ManifestServiceUnavailableError

logger = logging.getLogger(__name__)


class StateManagerClient:
    """HTTP client for State Manager API.

    The State Manager persists manifest state and provides reconciliation
    capabilities for the mothership to track deployed resources across boots.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.runpod.io",
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize State Manager client.

        Args:
            api_key: RunPod API key. Defaults to RUNPOD_API_KEY env var.
            base_url: Base URL for State Manager API.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts.

        Raises:
            ValueError: If api_key not provided and env var not set.
        """
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key required: pass api_key or set RUNPOD_API_KEY environment variable"
            )

        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: RunpodGraphQLClient

    async def get_persisted_manifest(
        self, mothership_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch persisted manifest from State Manager.

        Args:
            mothership_id: ID of the mothership endpoint.

        Returns:
            Manifest dict or None if not found (first boot).

        Raises:
            ManifestServiceUnavailableError: If State Manager unavailable after retries.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with RunpodGraphQLClient() as client:
                    _, manifest = await self._fetch_build_and_manifest(
                        client, mothership_id
                    )

                logger.debug(f"Persisted manifest loaded for {mothership_id}")
                return manifest

            except (
                asyncio.TimeoutError,
                ManifestServiceUnavailableError,
                Exception,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"State Manager request failed (attempt {attempt + 1}): {e}, "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue

        raise ManifestServiceUnavailableError(
            f"Failed to fetch persisted manifest after {self.max_retries} attempts: "
            f"{last_exception}"
        )

    async def update_resource_state(
        self,
        mothership_id: str,
        resource_name: str,
        resource_data: Dict[str, Any],
    ) -> None:
        """Update single resource entry in State Manager.

        Args:
            mothership_id: ID of the mothership endpoint.
            resource_name: Name of the resource.
            resource_data: Resource metadata (config_hash, endpoint_url, status, etc).

        Raises:
            ManifestServiceUnavailableError: If State Manager unavailable.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with RunpodGraphQLClient() as client:
                    build_id, manifest = await self._fetch_build_and_manifest(
                        client, mothership_id
                    )
                    resources = manifest.setdefault("resources", {})
                    existing = resources.get(resource_name)
                    if not isinstance(existing, dict):
                        existing = {}
                    resources[resource_name] = {**existing, **resource_data}
                    await client.update_build_manifest(build_id, manifest)

                logger.debug(
                    f"Updated resource state in State Manager: {mothership_id}/{resource_name}"
                )
                return

            except (
                asyncio.TimeoutError,
                ManifestServiceUnavailableError,
                Exception,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"State Manager request failed (attempt {attempt + 1}): {e}, "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue

        raise ManifestServiceUnavailableError(
            f"Failed to update resource state after {self.max_retries} attempts: "
            f"{last_exception}"
        )

    async def remove_resource_state(
        self, mothership_id: str, resource_name: str
    ) -> None:
        """Remove resource entry from State Manager.

        Args:
            mothership_id: ID of the mothership endpoint.
            resource_name: Name of the resource.

        Raises:
            ManifestServiceUnavailableError: If State Manager unavailable.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with RunpodGraphQLClient() as client:
                    build_id, manifest = await self._fetch_build_and_manifest(
                        client, mothership_id
                    )
                    resources = manifest.get("resources") or {}
                    resources.pop(resource_name, None)
                    manifest["resources"] = resources
                    await client.update_build_manifest(build_id, manifest)

                logger.debug(
                    f"Removed resource state from State Manager: {mothership_id}/{resource_name}"
                )
                return

            except (
                asyncio.TimeoutError,
                ManifestServiceUnavailableError,
                Exception,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"State Manager request failed (attempt {attempt + 1}): {e}, "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue

        raise ManifestServiceUnavailableError(
            f"Failed to remove resource state after {self.max_retries} attempts: "
            f"{last_exception}"
        )

    async def _fetch_build_and_manifest(
        self, client: RunpodGraphQLClient, mothership_id: str
    ) -> tuple[str, Dict[str, Any]]:
        environment = await client.get_flash_environment(
            {"flashEnvironmentId": mothership_id}
        )
        build_id = environment.get("activeBuildId")
        if not build_id:
            raise ManifestServiceUnavailableError(
                f"active build for environment {mothership_id} not found"
            )
        build = await client.get_flash_build(build_id)
        manifest = build.get("manifest")
        if not manifest:
            raise ManifestServiceUnavailableError(
                f"manifest not found for build {build.get('id', build_id)}"
            )
        return build_id, manifest

    async def close(self) -> None:
        """Close HTTP session."""
        return

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
