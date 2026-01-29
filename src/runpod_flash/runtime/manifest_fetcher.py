"""Manifest fetcher with RunPod GQL integration and caching.

This module provides manifest fetching from RunPod GraphQL API (source of truth)
with local file caching and fallback.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .config import DEFAULT_CACHE_TTL
from .generic_handler import load_manifest

logger = logging.getLogger(__name__)


class ManifestFetcher:
    """Fetches and caches manifest from RunPod GraphQL API.

    RunPod's GraphQL API is the source of truth for manifest data. This
    fetcher pulls from it using RunpodGraphQLClient, caches locally, and
    falls back to local file if RunPod API is unavailable.
    """

    def __init__(
        self,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        manifest_path: Optional[Path] = None,
    ):
        """Initialize manifest fetcher.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 300)
            manifest_path: Optional path to local manifest file
        """
        self.cache_ttl = cache_ttl
        self.manifest_path = manifest_path

        # Cache state
        self._cached_manifest: Optional[Dict[str, Any]] = None
        self._cache_loaded_at: float = 0
        self._cache_lock = asyncio.Lock()

    async def get_manifest(
        self,
        mothership_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get manifest from cache or fetch from RunPod GraphQL API.

        Flow:
        1. Check if cached and not expired → return cached
        2. If expired/not cached → fetch from RunPod GraphQL API
        3. Update local flash_manifest.json with fetched data
        4. Cache the result
        5. Return manifest

        If RunPod GQL fetch fails, falls back to local file.

        Args:
            mothership_id: Optional mothership endpoint ID for tracking

        Returns:
            Manifest dictionary or None if unavailable
        """
        async with self._cache_lock:
            now = time.time()
            cache_age = now - self._cache_loaded_at

            # Return cached if still valid
            if self._cached_manifest and cache_age < self.cache_ttl:
                logger.debug(
                    f"Serving cached manifest (age: {cache_age:.1f}s, "
                    f"TTL: {self.cache_ttl}s)"
                )
                return self._cached_manifest

            # Cache expired or not loaded - fetch from RunPod GQL
            logger.debug("Cache expired or empty, fetching from RunPod GraphQL API")

            try:
                # Fetch from RunPod GraphQL API (placeholder)
                manifest = await self._fetch_from_gql(mothership_id)

                # Update local flash_manifest.json
                if manifest:
                    self._update_local_file(manifest)

                    # Update cache
                    self._cached_manifest = manifest
                    self._cache_loaded_at = now

                    logger.info(
                        f"Manifest fetched from RunPod GQL and cached "
                        f"({len(manifest.get('resources', {}))} resources)"
                    )
                    return manifest

            except NotImplementedError:
                logger.debug(
                    "RunPod GQL fetch not implemented, falling back to local file"
                )
            except Exception as e:
                logger.warning(
                    f"RunPod GQL fetch failed: {e}, falling back to local file"
                )

            # Fallback: load from local file
            manifest = load_manifest(self.manifest_path)
            if manifest:
                # Cache the fallback manifest
                self._cached_manifest = manifest
                self._cache_loaded_at = now
                logger.debug("Loaded and cached manifest from local file")

            return manifest

    async def _fetch_from_gql(
        self,
        mothership_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch manifest from RunPod GraphQL API.

        TBD: Future implementation will query RunPod's GraphQL API
        to retrieve the manifest configuration.

        Args:
            mothership_id: Optional mothership endpoint ID

        Returns:
            Manifest dictionary from RunPod GQL

        Raises:
            NotImplementedError: Placeholder for future implementation

        Note:
            Future implementation will use RunpodGraphQLClient:

            ```python
            async with RunpodGraphQLClient() as client:
                query = '''
                query GetManifest($mothershipId: ID!) {
                    getManifest(mothershipId: $mothershipId) {
                        version
                        projectName
                        generatedAt
                        resources
                        functionRegistry
                    }
                }
                '''
                result = await client.execute(query, {"mothershipId": mothership_id})
                return result["data"]["getManifest"]
            ```
        """
        raise NotImplementedError(
            "RunPod manifest query not yet implemented. "
            "Falling back to local flash_manifest.json file."
        )

    def _update_local_file(self, manifest: Dict[str, Any]) -> None:
        """Update local flash_manifest.json with fetched data.

        Args:
            manifest: Manifest dictionary to write
        """
        try:
            # Determine file path
            if self.manifest_path:
                file_path = self.manifest_path
            else:
                file_path = Path.cwd() / "flash_manifest.json"

            # Write manifest to file
            with open(file_path, "w") as f:
                json.dump(manifest, f, indent=2)

            logger.debug(f"Updated local manifest file: {file_path}")

        except Exception as e:
            logger.warning(f"Failed to update local manifest file: {e}")
            # Non-critical error - cached manifest still valid

    def invalidate_cache(self) -> None:
        """Manually invalidate the cache.

        Next get_manifest() call will fetch from GQL.
        """
        self._cache_loaded_at = 0
        logger.debug("Manifest cache invalidated")
