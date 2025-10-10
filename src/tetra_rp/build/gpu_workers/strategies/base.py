"""
Base deployment strategy interface with Pydantic models.

Defines the abstract interface that all deployment strategies must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class StrategyType(str, Enum):
    """Available deployment strategy types."""

    IMAGE = "image"  # Full Docker image build with baked code
    TARBALL = "tarball"  # Tarball download at runtime


class DeploymentArtifact(BaseModel):
    """
    Artifact produced by deployment strategy.

    This represents what gets deployed (image reference, tarball path, etc.)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    strategy_type: StrategyType
    artifact_reference: str = Field(
        ..., description="Main artifact reference (image name, tarball key, etc.)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Strategy-specific metadata"
    )
    size_bytes: Optional[int] = Field(None, description="Artifact size in bytes")
    code_hash: Optional[str] = Field(None, description="Hash of deployed code")


class DeployedResource(BaseModel):
    """
    Result of deploying a resource to a platform.

    Contains information about the deployed resource.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    resource_id: Optional[str] = None
    endpoint_url: Optional[str] = None
    artifact: DeploymentArtifact
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeploymentConfig(BaseModel):
    """
    Base configuration for deployment strategies.

    Contains common configuration shared across all strategies.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    strategy_type: StrategyType
    base_image: str = Field(
        default="runpod/worker-v1-tetra:latest",
        description="Base Docker image for GPU workers",
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Python dependencies"
    )
    env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    platform: str = Field(default="linux/amd64", description="Docker platform")


class DeploymentStrategy(ABC):
    """
    Abstract base class for deployment strategies.

    All deployment strategies must implement this interface.

    Strategy Pattern:
    - ImageBuildStrategy: Bakes code into Docker image
    - TarballStrategy: Creates tarball, downloads at runtime
    - Future: S3Strategy, GitStrategy, HybridStrategy, etc.
    """

    def __init__(self, config: DeploymentConfig):
        """
        Initialize strategy with configuration.

        Args:
            config: Deployment configuration
        """
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate strategy-specific configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def prepare_deployment(
        self, func_or_class: Any, name: str
    ) -> DeploymentArtifact:
        """
        Prepare deployment artifact (image, tarball, etc.).

        Args:
            func_or_class: Python function or class to deploy
            name: Name for the deployment

        Returns:
            DeploymentArtifact with artifact reference and metadata

        Raises:
            RuntimeError: If preparation fails
        """
        pass

    @abstractmethod
    async def apply_to_resource(
        self, resource_config: Any, artifact: DeploymentArtifact
    ) -> Any:
        """
        Apply deployment artifact to resource configuration.

        Modifies resource_config in place to use the deployment artifact.

        Args:
            resource_config: Resource configuration to modify
            artifact: Deployment artifact to apply

        Returns:
            Modified resource configuration
        """
        pass

    def get_strategy_type(self) -> StrategyType:
        """Get the strategy type."""
        return self.config.strategy_type

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(strategy={self.config.strategy_type.value})"
