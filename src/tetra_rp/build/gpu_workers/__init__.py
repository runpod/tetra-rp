"""
GPU Worker deployment system - Tarball Strategy.

Flash CLI uses tarball-based deployment for GPU workers.
"""

from .strategies import (
    # Base types
    DeploymentStrategy,
    DeploymentArtifact,
    DeploymentConfig,
    StrategyType,
    # Tarball Strategy
    TarballStrategy,
    TarballStrategyConfig,
)

# Shared components
from .code_packager import CodePackager, PackageInfo
from .volume_manager import UploadResult, VolumeConfig, VolumeManager

__all__ = [
    # Base types
    "DeploymentStrategy",
    "DeploymentArtifact",
    "DeploymentConfig",
    "StrategyType",
    # Tarball Strategy
    "TarballStrategy",
    "TarballStrategyConfig",
    # Shared Components
    "CodePackager",
    "PackageInfo",
    "VolumeManager",
    "VolumeConfig",
    "UploadResult",
]
