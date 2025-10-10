"""
Deployment strategies for GPU workers.

Flash CLI uses tarball-based deployment strategy.

Usage:
    from tetra_rp.build.gpu_workers.strategies import TarballStrategyConfig

    config = TarballStrategyConfig(
        upload_to_storage=True,
        storage_endpoint="s3.amazonaws.com",
        storage_bucket="my-bucket"
    )
    strategy = TarballStrategy(config=config)
    artifact = await strategy.prepare_deployment(MyClass, "my-worker")
    strategy.apply_to_resource(resource_config, artifact)
"""

from .base import (
    DeploymentArtifact,
    DeploymentConfig,
    DeploymentStrategy,
    DeployedResource,
    StrategyType,
)
from .tarball_strategy import TarballStrategy, TarballStrategyConfig

__all__ = [
    # Base classes
    "DeploymentStrategy",
    "DeploymentConfig",
    "DeploymentArtifact",
    "DeployedResource",
    "StrategyType",
    # Tarball Strategy
    "TarballStrategy",
    "TarballStrategyConfig",
]
