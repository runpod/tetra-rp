"""HTTP client for mothership manifest directory API."""

import asyncio
import logging
import os
from typing import Dict, Optional

try:
    import httpx
except ImportError:
    httpx = None

from .config import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT
from .exceptions import ManifestServiceUnavailableError

logger = logging.getLogger(__name__)


class ManifestClient:
    """HTTP client for querying mothership manifest directory service.

    Fetches the endpoint registry that maps resource_config names to their
    deployment URLs. This is the "manifest directory service" - an endpoint
    registry showing where resources are deployed.

    The directory maps resource_config names to their endpoint URLs.
    Example: {"gpu_config": "https://api.runpod.io/v2/abc123"}
    """

    def __init__(
        self,
        mothership_url: Optional[str] = None,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize manifest client.

        Args:
            mothership_url: Base URL of mothership endpoint. Defaults to
                FLASH_MOTHERSHIP_URL environment variable.
            timeout: Request timeout in seconds (default: 10).
            max_retries: Maximum retry attempts (default: 3).

        Raises:
            ValueError: If mothership_url not provided and env var not set.
        """
        self.mothership_url = mothership_url or os.getenv("FLASH_MOTHERSHIP_URL")
        if not self.mothership_url:
            raise ValueError(
                "mothership_url required: pass mothership_url or set "
                "FLASH_MOTHERSHIP_URL environment variable"
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def get_directory(self) -> Dict[str, str]:
        """Fetch endpoint directory from mothership.

        Returns:
            Dictionary mapping resource_config_name → endpoint_url.
            Example: {"gpu_config": "https://api.runpod.io/v2/abc123"}

        Raises:
            ManifestServiceUnavailableError: If manifest directory service unavailable after retries.
        """
        if httpx is None:
            raise ImportError(
                "httpx required for ManifestClient. Install with: pip install httpx"
            )

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.get(
                    f"{self.mothership_url}/directory",
                    timeout=self.timeout,
                )

                if response.status_code >= 400:
                    raise ManifestServiceUnavailableError(
                        f"Directory API returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

                data = response.json()
                if "directory" not in data:
                    raise ManifestServiceUnavailableError(
                        "Invalid directory response: missing 'directory' key"
                    )

                directory = data["directory"]
                logger.debug(f"Directory loaded: {len(directory)} endpoints")
                return directory

            except (
                asyncio.TimeoutError,
                ManifestServiceUnavailableError,
                Exception,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"Manifest service request failed (attempt {attempt + 1}): {e}, "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue

        raise ManifestServiceUnavailableError(
            f"Failed to fetch manifest directory after {self.max_retries} attempts: {last_exception}"
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
