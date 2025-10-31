"""
Docker registry management.

Handles registry configuration, image pushing, and registry operations.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Docker registry configuration."""

    registry_url: Optional[str] = None
    skip_push: bool = False

    @classmethod
    def from_environment(cls) -> "RegistryConfig":
        """
        Create registry config from environment variables.

        Environment variables:
            TETRA_DOCKER_REGISTRY: Registry URL (e.g., docker.io/myuser)
            TETRA_SKIP_PUSH: Skip push for fast local testing (true/false)

        Returns:
            RegistryConfig instance
        """
        registry = os.getenv("TETRA_DOCKER_REGISTRY")
        skip_push = os.getenv("TETRA_SKIP_PUSH", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        return cls(registry_url=registry, skip_push=skip_push)

    def get_registry_prefix(self) -> Optional[str]:
        """
        Get registry prefix for image names.

        Returns:
            Registry prefix with trailing slash, or None if not configured
        """
        if not self.registry_url:
            return None

        # Ensure it ends with /
        return (
            self.registry_url
            if self.registry_url.endswith("/")
            else f"{self.registry_url}/"
        )

    def should_push(self) -> bool:
        """Check if images should be pushed to registry."""
        return self.registry_url is not None and not self.skip_push


@dataclass
class PushResult:
    """Result of Docker image push."""

    success: bool
    image: str
    message: Optional[str] = None


class RegistryManager:
    """Manage Docker registry operations."""

    def __init__(self, config: Optional[RegistryConfig] = None):
        """
        Initialize registry manager.

        Args:
            config: Registry configuration (defaults to environment-based)
        """
        self.config = config or RegistryConfig.from_environment()

    def get_full_image_name(self, image_name: str, image_tag: str) -> str:
        """
        Get full image name with registry prefix.

        Args:
            image_name: Base image name
            image_tag: Image tag

        Returns:
            Full image name (with registry if configured)
        """
        local_image = f"{image_name}:{image_tag}"

        if prefix := self.config.get_registry_prefix():
            return f"{prefix}{local_image}"

        return local_image

    def push_image(self, image: str) -> PushResult:
        """
        Push image to registry.

        Args:
            image: Full image name to push

        Returns:
            PushResult with success status
        """
        if not self.config.should_push():
            if self.config.skip_push:
                log.warning("TETRA_SKIP_PUSH=true - skipping push")
                log.warning(f"   Image {image} is LOCAL ONLY")
                log.warning("   RunPod deployment will fail unless you manually push")
                return PushResult(
                    success=True, image=image, message="Push skipped (TETRA_SKIP_PUSH)"
                )
            else:
                log.warning("No registry configured - image is local only")
                log.warning(
                    "Set TETRA_DOCKER_REGISTRY env var to enable automatic push"
                )
                log.warning("Example: export TETRA_DOCKER_REGISTRY=docker.io/myuser")
                return PushResult(
                    success=True, image=image, message="No registry configured"
                )

        log.info(f"Pushing to registry: {image}")
        log.info("This may take several minutes for large base images...")

        try:
            # Push to registry (show progress in stdout)
            subprocess.run(["docker", "push", image], check=True)

            log.info("Image pushed successfully")
            return PushResult(success=True, image=image, message="Push successful")

        except subprocess.CalledProcessError:
            log.error("Docker push failed")
            return PushResult(success=False, image=image, message="Push failed")
