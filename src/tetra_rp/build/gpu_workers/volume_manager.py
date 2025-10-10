"""
RunPod network volume management for S3-compatible storage.

Handles uploading/downloading tarballs to/from RunPod network volumes.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class VolumeConfig:
    """Configuration for RunPod network volume access."""

    volume_id: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    bucket_name: Optional[str] = None

    @classmethod
    def from_environment(cls) -> "VolumeConfig":
        """
        Create volume config from environment variables.

        Environment variables:
            RUNPOD_VOLUME_ID: Network volume ID
            RUNPOD_VOLUME_ENDPOINT: S3-compatible endpoint URL
            RUNPOD_VOLUME_ACCESS_KEY: S3 access key
            RUNPOD_VOLUME_SECRET_KEY: S3 secret key
            RUNPOD_VOLUME_BUCKET: S3 bucket name (defaults to 'tetra-code')

        Returns:
            VolumeConfig instance
        """
        return cls(
            volume_id=os.getenv("RUNPOD_VOLUME_ID"),
            endpoint_url=os.getenv("RUNPOD_VOLUME_ENDPOINT"),
            access_key=os.getenv("RUNPOD_VOLUME_ACCESS_KEY"),
            secret_key=os.getenv("RUNPOD_VOLUME_SECRET_KEY"),
            bucket_name=os.getenv("RUNPOD_VOLUME_BUCKET", "tetra-code"),
        )

    def is_configured(self) -> bool:
        """Check if volume is properly configured for S3-compatible storage."""
        return all(
            [
                self.endpoint_url,
                self.access_key,
                self.secret_key,
                self.bucket_name,
            ]
        )


@dataclass
class UploadResult:
    """Result of tarball upload."""

    success: bool
    s3_key: str
    volume_path: str
    message: str
    size_bytes: int = 0


class VolumeManager:
    """
    Manage RunPod network volume operations.

    Uses S3-compatible API (boto3) for fast uploads/downloads.
    """

    def __init__(self, config: Optional[VolumeConfig] = None):
        """
        Initialize volume manager.

        Args:
            config: Volume configuration (defaults to environment-based)
        """
        self.config = config or VolumeConfig.from_environment()
        self._s3_client = None

    def _get_s3_client(self):
        """Get or create S3 client for volume access."""
        if self._s3_client is not None:
            return self._s3_client

        if not self.config.is_configured():
            raise ValueError(
                "Volume not configured. Set RUNPOD_VOLUME_* environment variables."
            )

        try:
            import boto3

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.config.endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name="eu-ro-1",
            )

            log.debug(f"S3 client initialized for volume: {self.config.volume_id}")
            return self._s3_client

        except ImportError:
            raise ImportError(
                "boto3 required for volume management. Install with: pip install boto3"
            )

    def upload_tarball(
        self, tarball_path: Path, s3_key: Optional[str] = None
    ) -> UploadResult:
        """
        Upload tarball to RunPod network volume.

        Args:
            tarball_path: Path to tarball file
            s3_key: S3 key (defaults to filename)

        Returns:
            UploadResult with upload status
        """
        if not self.config.is_configured():
            log.warning("Volume not configured - skipping upload")
            log.warning("   Set RUNPOD_VOLUME_* env vars to enable volume uploads")
            return UploadResult(
                success=False,
                s3_key="",
                volume_path="",
                message="Volume not configured",
            )

        if not tarball_path.exists():
            return UploadResult(
                success=False,
                s3_key="",
                volume_path="",
                message=f"Tarball not found: {tarball_path}",
            )

        # Use filename as S3 key if not specified
        if s3_key is None:
            s3_key = tarball_path.name

        # Get file size
        size_bytes = tarball_path.stat().st_size
        size_kb = size_bytes / 1024

        log.info(f"Uploading to volume: {s3_key} ({size_kb:.1f} KB)")

        try:
            s3 = self._get_s3_client()

            # Upload with progress callback
            s3.upload_file(
                str(tarball_path),
                self.config.bucket_name,
                s3_key,
                Callback=self._upload_progress_callback(size_bytes),
            )

            volume_path = f"s3://{self.config.bucket_name}/{s3_key}"

            log.info(f"Upload complete: {volume_path}")

            return UploadResult(
                success=True,
                s3_key=s3_key,
                volume_path=volume_path,
                message="Upload successful",
                size_bytes=size_bytes,
            )

        except Exception as e:
            log.error(f"Upload failed: {e}")
            return UploadResult(
                success=False,
                s3_key=s3_key,
                volume_path="",
                message=f"Upload failed: {e}",
            )

    def download_tarball(self, s3_key: str, output_path: Path) -> bool:
        """
        Download tarball from RunPod network volume.

        Args:
            s3_key: S3 key of tarball
            output_path: Local path to save tarball

        Returns:
            True if successful, False otherwise
        """
        if not self.config.is_configured():
            log.error("Volume not configured")
            return False

        log.info(f"📥 Downloading from volume: {s3_key}")

        try:
            s3 = self._get_s3_client()

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            s3.download_file(self.config.bucket_name, s3_key, str(output_path))

            size_kb = output_path.stat().st_size / 1024
            log.info(f"Downloaded: {output_path.name} ({size_kb:.1f} KB)")

            return True

        except Exception as e:
            log.error(f"Download failed: {e}")
            return False

    def tarball_exists(self, s3_key: str) -> bool:
        """
        Check if tarball exists in volume.

        Args:
            s3_key: S3 key to check

        Returns:
            True if exists, False otherwise
        """
        if not self.config.is_configured():
            return False

        try:
            s3 = self._get_s3_client()
            s3.head_object(Bucket=self.config.bucket_name, Key=s3_key)
            return True
        except Exception:
            return False

    def _upload_progress_callback(self, total_bytes: int):
        """Create callback for upload progress tracking."""
        uploaded = [0]  # Use list to allow modification in closure

        def callback(bytes_transferred):
            uploaded[0] += bytes_transferred
            percent = (uploaded[0] / total_bytes) * 100
            if uploaded[0] == total_bytes or percent % 25 < 1:
                log.debug(f"   Upload progress: {percent:.0f}%")

        return callback
