"""
Docker image building operations.

Handles building Docker images with platform targeting.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ImageBuildConfig:
    """Configuration for Docker image build."""

    build_dir: Path
    image_name: str
    image_tag: str
    platform: str = "linux/amd64"


@dataclass
class BuildResult:
    """Result of Docker image build."""

    success: bool
    local_image: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class ImageBuilder:
    """Build Docker images with platform targeting."""

    def build(self, config: ImageBuildConfig) -> BuildResult:
        """
        Build Docker image.

        Args:
            config: Build configuration

        Returns:
            BuildResult with success status and output

        Raises:
            RuntimeError: If Docker build fails
        """
        local_image = f"{config.image_name}:{config.image_tag}"

        log.info(f"Building Docker image: {local_image}")
        log.info(f"   Platform: {config.platform}")
        log.info(f"   Build dir: {config.build_dir}")

        try:
            result = subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    config.platform,
                    "-t",
                    local_image,
                    "-f",
                    "Dockerfile",
                    ".",
                ],
                cwd=config.build_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            log.info(f"Image built successfully: {local_image}")

            return BuildResult(
                success=True,
                local_image=local_image,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        except subprocess.CalledProcessError as e:
            log.error("Docker build failed:")
            log.error(e.stderr)

            return BuildResult(
                success=False,
                local_image=local_image,
                stdout=e.stdout,
                stderr=e.stderr,
            )

    def tag_image(self, source: str, target: str) -> bool:
        """
        Tag a Docker image.

        Args:
            source: Source image name
            target: Target image name

        Returns:
            True if successful, False otherwise
        """
        log.debug(f"Tagging image: {source} -> {target}")

        try:
            subprocess.run(
                ["docker", "tag", source, target],
                check=True,
                capture_output=True,
            )
            log.debug("Tagged successfully")
            return True

        except subprocess.CalledProcessError as e:
            log.error(
                f"Tag failed: {e.stderr.decode() if e.stderr else 'unknown error'}"
            )
            return False
