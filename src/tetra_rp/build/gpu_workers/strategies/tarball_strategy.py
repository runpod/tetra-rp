"""
Tarball Deployment Strategy.

Creates tarball and downloads at runtime - serverless approach.
Pro: Fast deployments, small artifacts (KBs), like AWS Lambda
Con: Cold start overhead, runtime dependency on storage
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from pydantic import Field

from .base import (
    DeploymentArtifact,
    DeploymentConfig,
    DeploymentStrategy,
    StrategyType,
)
from ..code_packager import CodePackager
from ...shared.code_extractor import CodeExtractor
from ..volume_manager import VolumeManager

log = logging.getLogger(__name__)


class TarballStrategyConfig(DeploymentConfig):
    """Configuration specific to tarball strategy."""

    strategy_type: StrategyType = Field(default=StrategyType.TARBALL, frozen=True)
    upload_to_storage: bool = Field(
        default=False, description="Upload tarball to S3/storage"
    )
    storage_endpoint: Optional[str] = Field(
        None, description="S3-compatible storage endpoint"
    )
    storage_bucket: Optional[str] = Field(None, description="Storage bucket name")
    storage_access_key: Optional[str] = Field(
        None, description="Storage access key (from env if empty)"
    )
    storage_secret_key: Optional[str] = Field(
        None, description="Storage secret key (from env if empty)"
    )


class TarballStrategy(DeploymentStrategy):
    """
    Deployment strategy that creates tarball for runtime download.

    Serverless approach where code is packaged as tarball and downloaded
    by workers at startup. Similar to AWS Lambda, Google Cloud Functions.

    Use when:
    - Need fast deployments (KBs vs GBs)
    - Code changes frequently during development
    - Want serverless-style cold start
    - Have S3-compatible storage available
    """

    def __init__(self, config: TarballStrategyConfig):
        """Initialize tarball strategy."""
        super().__init__(config)
        self.config: TarballStrategyConfig = config
        self.code_extractor = CodeExtractor()
        self.code_packager = CodePackager()
        self.volume_manager = VolumeManager() if config.upload_to_storage else None

    def _validate_config(self) -> None:
        """Validate tarball strategy configuration."""
        if self.config.upload_to_storage:
            if not self.config.storage_endpoint:
                raise ValueError(
                    "storage_endpoint required when upload_to_storage=True"
                )
            if not self.config.storage_bucket:
                raise ValueError("storage_bucket required when upload_to_storage=True")

    async def prepare_deployment(
        self, func_or_class: Any, name: str
    ) -> DeploymentArtifact:
        """
        Create tarball package for runtime download.

        Args:
            func_or_class: Python function or class to deploy
            name: Name for the tarball

        Returns:
            DeploymentArtifact with tarball reference
        """
        log.info(f"Creating tarball package: {name}")

        # Extract code
        extracted_code = self.code_extractor.extract(func_or_class)
        log.info(f"   Code hash: {extracted_code.code_hash}")

        # Create tarball
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            package_info = self.code_packager.create_package(
                extracted_code=extracted_code,
                dependencies=self.config.dependencies,
                output_dir=output_dir,
            )

            log.info(f"   Tarball: {package_info.tarball_path}")
            log.info(f"   Size: {package_info.size_bytes / 1024:.2f} KB")

            # Upload to storage if configured
            storage_key = None
            if self.config.upload_to_storage and self.volume_manager:
                storage_key = f"tetra/code/{name}-{extracted_code.code_hash}.tar.gz"

                upload_result = self.volume_manager.upload_tarball(
                    tarball_path=package_info.tarball_path,
                    s3_key=storage_key,
                )

                if not upload_result.success:
                    raise RuntimeError(
                        f"Tarball upload failed: {upload_result.message}"
                    )

                log.info(f"Tarball uploaded: {storage_key}")

            return DeploymentArtifact(
                strategy_type=StrategyType.TARBALL,
                artifact_reference=storage_key or str(package_info.tarball_path),
                code_hash=extracted_code.code_hash,
                size_bytes=package_info.size_bytes,
                metadata={
                    "tarball_name": package_info.tarball_name,
                    "uploaded": storage_key is not None,
                    "storage_key": storage_key,
                    "local_path": str(package_info.tarball_path),
                },
            )

    async def apply_to_resource(
        self, resource_config: Any, artifact: DeploymentArtifact
    ) -> Any:
        """
        Apply tarball configuration to resource.

        Args:
            resource_config: Resource configuration to modify
            artifact: Deployment artifact with tarball reference

        Returns:
            Modified resource configuration
        """
        # Use base image (not custom image)
        resource_config.imageName = self.config.base_image

        # Set environment variables for tarball loading
        if not hasattr(resource_config, "env"):
            resource_config.env = {}

        resource_config.env.update(self.config.env_vars)
        resource_config.env["TETRA_BAKED_MODE"] = "true"
        resource_config.env["TETRA_DEPLOYMENT_STRATEGY"] = "tarball"

        # Set tarball reference
        if artifact.metadata.get("uploaded"):
            # Downloaded from storage at runtime
            resource_config.env["TETRA_CODE_TARBALL"] = artifact.artifact_reference
            resource_config.env["RUNPOD_VOLUME_ENDPOINT"] = (
                self.config.storage_endpoint or ""
            )
            resource_config.env["RUNPOD_VOLUME_BUCKET"] = (
                self.config.storage_bucket or ""
            )
            resource_config.env["RUNPOD_VOLUME_ACCESS_KEY"] = (
                self.config.storage_access_key or ""
            )
            resource_config.env["RUNPOD_VOLUME_SECRET_KEY"] = (
                self.config.storage_secret_key or ""
            )
            log.info("Applied tarball strategy (storage download)")
            log.info(f"   Storage key: {artifact.artifact_reference}")
        else:
            # Local tarball (for testing)
            resource_config.env["TETRA_CODE_TARBALL_LOCAL"] = (
                artifact.artifact_reference
            )
            log.info("Applied tarball strategy (local)")
            log.info(f"   Local path: {artifact.artifact_reference}")

        return resource_config
