"""HTTP client for State Manager API to persist and reconcile manifests."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

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
        self._client: Optional[httpx.AsyncClient] = None

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
        if httpx is None:
            raise ImportError(
                "httpx required for StateManagerClient. Install with: pip install httpx"
            )

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.get(
                    f"{self.base_url}/api/v1/flash/manifests/{mothership_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    logger.debug(
                        f"No persisted manifest found for {mothership_id} (first boot)"
                    )
                    return None

                if response.status_code >= 400:
                    raise ManifestServiceUnavailableError(
                        f"State Manager returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

                data = response.json()
                logger.debug(f"Persisted manifest loaded for {mothership_id}")
                return data

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
        if httpx is None:
            raise ImportError(
                "httpx required for StateManagerClient. Install with: pip install httpx"
            )

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.put(
                    f"{self.base_url}/api/v1/flash/manifests/{mothership_id}/resources/{resource_name}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=resource_data,
                    timeout=self.timeout,
                )

                if response.status_code >= 400:
                    raise ManifestServiceUnavailableError(
                        f"State Manager returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

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
        if httpx is None:
            raise ImportError(
                "httpx required for StateManagerClient. Install with: pip install httpx"
            )

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.delete(
                    f"{self.base_url}/api/v1/flash/manifests/{mothership_id}/resources/{resource_name}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout,
                )

                if response.status_code >= 400:
                    raise ManifestServiceUnavailableError(
                        f"State Manager returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(self.timeout)
            self._client = httpx.AsyncClient(timeout=timeout)

        return self._client

    async def close(self) -> None:
        """Close HTTP session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
