"""HTTP client for mothership directory API."""

import asyncio
import logging
import os
from typing import Dict, Optional

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class DirectoryUnavailableError(Exception):
    """Raised when directory service is unavailable."""

    pass


class DirectoryClient:
    """HTTP client for querying mothership directory.

    The directory maps resource_config names to their endpoint URLs.
    Example: {"gpu_config": "https://api.runpod.io/v2/abc123"}
    """

    def __init__(
        self,
        mothership_url: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """Initialize directory client.

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
            DirectoryUnavailableError: If directory service unavailable after retries.
        """
        if httpx is None:
            raise ImportError(
                "httpx required for DirectoryClient. Install with: pip install httpx"
            )

        for attempt in range(self.max_retries):
            try:
                client = await self._get_client()
                response = await client.get(
                    f"{self.mothership_url}/directory",
                    timeout=self.timeout,
                )

                if response.status_code >= 400:
                    raise DirectoryUnavailableError(
                        f"Directory API returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

                data = response.json()
                directory = data.get("directory", {})

                logger.debug(f"Directory loaded: {len(directory)} endpoints")
                return directory

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"Directory request timed out (attempt {attempt + 1}), "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise DirectoryUnavailableError(
                    f"Directory request timed out after {self.max_retries} attempts"
                )

            except Exception as e:
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        f"Directory request failed (attempt {attempt + 1}): {e}, "
                        f"retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise DirectoryUnavailableError(
                    f"Failed to fetch directory after {self.max_retries} attempts: {e}"
                )

        raise DirectoryUnavailableError("Exhausted retries for directory fetch")

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
