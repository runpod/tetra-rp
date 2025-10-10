"""
Image cache management for production builds.

Provides intelligent caching to avoid unnecessary rebuilds when code hasn't changed.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached image information."""

    image_name: str
    image_tag: str
    full_image: str
    code_hash: str
    callable_name: str
    exists_locally: bool = False
    exists_in_registry: bool = False


class ImageCache:
    """
    Manage build cache to avoid unnecessary rebuilds.

    Checks both local Docker images and remote registry to determine
    if an image with the same code hash already exists.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize image cache.

        Args:
            cache_file: Path to cache metadata file (defaults to ~/.tetra/build_cache.json)
        """
        if cache_file is None:
            cache_dir = Path.home() / ".tetra"
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / "build_cache.json"

        self.cache_file = cache_file
        self._cache_data = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache metadata from disk."""
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Failed to load cache file: {e}")
            return {}

    def _save_cache(self) -> None:
        """Save cache metadata to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self._cache_data, f, indent=2)
        except IOError as e:
            log.warning(f"Failed to save cache file: {e}")

    def get_cached_image(
        self, callable_name: str, code_hash: str
    ) -> Optional[CacheEntry]:
        """
        Check if cached image exists for given callable and code hash.

        Args:
            callable_name: Name of function/class
            code_hash: Hash of source code

        Returns:
            CacheEntry if found, None otherwise
        """
        cache_key = f"{callable_name}:{code_hash}"

        # Check cache metadata
        if cache_key not in self._cache_data:
            log.debug(f"Cache miss: {cache_key} not in cache metadata")
            return None

        cached = self._cache_data[cache_key]
        entry = CacheEntry(
            image_name=cached["image_name"],
            image_tag=cached["image_tag"],
            full_image=cached["full_image"],
            code_hash=code_hash,
            callable_name=callable_name,
        )

        log.debug(f"Cache metadata found for {cache_key}")

        # Verify image still exists
        entry.exists_locally = self._check_local_image(entry.full_image)
        entry.exists_in_registry = self._check_registry_image(entry.full_image)

        if entry.exists_locally or entry.exists_in_registry:
            log.info(f"Cache HIT: {entry.full_image}")
            log.info(
                f"   Local: {entry.exists_locally}, Registry: {entry.exists_in_registry}"
            )
            return entry
        else:
            log.info("Cache metadata exists but image not found, rebuilding")
            # Remove stale cache entry
            del self._cache_data[cache_key]
            self._save_cache()
            return None

    def store_image(
        self,
        callable_name: str,
        code_hash: str,
        image_name: str,
        image_tag: str,
        full_image: str,
    ) -> None:
        """
        Store image information in cache.

        Args:
            callable_name: Name of function/class
            code_hash: Hash of source code
            image_name: Base image name
            image_tag: Image tag
            full_image: Full image name with registry
        """
        cache_key = f"{callable_name}:{code_hash}"

        self._cache_data[cache_key] = {
            "callable_name": callable_name,
            "code_hash": code_hash,
            "image_name": image_name,
            "image_tag": image_tag,
            "full_image": full_image,
        }

        self._save_cache()
        log.debug(f"Cached image info: {cache_key} -> {full_image}")

    def invalidate(self, callable_name: str) -> int:
        """
        Invalidate all cached images for a callable.

        Args:
            callable_name: Name of function/class to invalidate

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [
            k for k in self._cache_data.keys() if k.startswith(f"{callable_name}:")
        ]

        for key in keys_to_remove:
            del self._cache_data[key]

        if keys_to_remove:
            self._save_cache()
            log.info(
                f"Invalidated {len(keys_to_remove)} cache entries for {callable_name}"
            )

        return len(keys_to_remove)

    def clear(self) -> int:
        """
        Clear entire cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache_data)
        self._cache_data = {}
        self._save_cache()
        log.info(f"Cleared {count} cache entries")
        return count

    def _check_local_image(self, image: str) -> bool:
        """
        Check if image exists in local Docker.

        Args:
            image: Full image name to check

        Returns:
            True if image exists locally
        """
        try:
            result = subprocess.run(
                ["docker", "images", "-q", image],
                capture_output=True,
                text=True,
                check=False,
            )
            exists = bool(result.stdout.strip())
            log.debug(f"Local image check for {image}: {exists}")
            return exists
        except (subprocess.SubprocessError, FileNotFoundError):
            log.debug(f"Failed to check local image: {image}")
            return False

    def _check_registry_image(self, image: str) -> bool:
        """
        Check if image exists in remote registry.

        Uses `docker manifest inspect` which doesn't pull the image.

        Args:
            image: Full image name to check

        Returns:
            True if image exists in registry
        """
        # Only check registry if image has registry prefix
        if "/" not in image or image.count("/") < 2:
            log.debug(f"Skipping registry check for local-only image: {image}")
            return False

        try:
            result = subprocess.run(
                ["docker", "manifest", "inspect", image],
                capture_output=True,
                text=True,
                check=False,
            )
            exists = result.returncode == 0
            log.debug(f"Registry image check for {image}: {exists}")
            return exists
        except (subprocess.SubprocessError, FileNotFoundError):
            log.debug(f"Failed to check registry image: {image}")
            return False
