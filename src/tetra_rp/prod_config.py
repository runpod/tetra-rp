"""
Production configuration loader for Flash CLI.

Handles loading build artifacts and configuring resources for baked execution mode.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from .core.resources import ServerlessResource

log = logging.getLogger(__name__)


class ProductionConfig:
    """Factory for loading and applying production configuration."""

    def __init__(self, artifacts_path: Optional[Path] = None):
        """
        Initialize production config loader.

        Args:
            artifacts_path: Path to build_artifacts.json. Defaults to .tetra/build_artifacts.json
        """
        self.artifacts_path = artifacts_path or Path.cwd() / ".tetra" / "build_artifacts.json"
        self._artifacts = None

    @property
    def artifacts(self) -> dict:
        """Load and cache build artifacts."""
        if self._artifacts is None:
            if not self.artifacts_path.exists():
                raise FileNotFoundError(
                    f"Build artifacts not found at {self.artifacts_path}. "
                    f"Run 'flash build' first."
                )
            with open(self.artifacts_path, "r") as f:
                self._artifacts = json.load(f)
        return self._artifacts

    def get_worker_config(self, worker_name: str) -> Optional[dict]:
        """
        Get worker configuration by name from build artifacts.

        Args:
            worker_name: Name of the worker class

        Returns:
            Worker configuration dict or None if not found
        """
        for worker in self.artifacts.get("workers", []):
            if worker.get("name") == worker_name:
                return worker
        return None

    def inject_config(self, resource_config: ServerlessResource, worker_name: str) -> None:
        """
        Inject production configuration into resource config.

        Modifies resource_config in-place by setting:
        - TETRA_BAKED_MODE=true
        - TETRA_TARBALL_PATH=/runpod-volume/{s3_key}
        - imageName from build artifacts

        Args:
            resource_config: The serverless resource configuration to modify
            worker_name: Name of the worker class for lookup
        """
        # Get worker configuration
        worker_config = self.get_worker_config(worker_name)
        if not worker_config:
            available = [w.get("name") for w in self.artifacts.get("workers", [])]
            raise ValueError(
                f"Worker '{worker_name}' not found in build artifacts. "
                f"Available workers: {available}"
            )

        # Extract tarball S3 key
        tarball_s3_key = worker_config.get("tarball_s3_key")
        if not tarball_s3_key:
            raise ValueError(f"No tarball_s3_key found for worker '{worker_name}'")

        # Configure environment variables for baked execution
        if resource_config.env is None:
            resource_config.env = {}

        resource_config.env.update({
            "TETRA_BAKED_MODE": "true",
            "TETRA_TARBALL_PATH": f"/runpod-volume/{tarball_s3_key}",
        })

        # Set base image from build artifacts
        base_image = worker_config.get("base_image")
        if base_image:
            resource_config.imageName = base_image

        # Attach network volume if volume ID is provided
        volume_id = os.getenv("RUNPOD_VOLUME_ID")
        if volume_id:
            resource_config.networkVolumeId = volume_id
            log.info(f"Attached network volume: {volume_id}")

        log.info(
            f"Production config applied for {worker_name}: "
            f"tarball={tarball_s3_key}, image={base_image}"
        )


def is_production_mode() -> bool:
    """Check if TETRA_PROD_MODE environment variable is enabled."""
    return os.getenv("TETRA_PROD_MODE", "").lower() in ("true", "1", "yes")


def apply_production_config(
    resource_config: ServerlessResource, worker_name: str
) -> None:
    """
    Apply production configuration if TETRA_PROD_MODE is enabled.

    Args:
        resource_config: The serverless resource configuration to modify
        worker_name: Name of the worker class

    Raises:
        FileNotFoundError: If build artifacts not found
        ValueError: If worker not found in artifacts
    """
    if not is_production_mode():
        log.debug("Production mode not enabled, skipping config injection")
        return

    try:
        config = ProductionConfig()
        config.inject_config(resource_config, worker_name)
    except Exception as e:
        log.error(f"Failed to apply production configuration: {e}")
        raise
