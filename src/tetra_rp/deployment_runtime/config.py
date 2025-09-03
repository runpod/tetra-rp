"""
Configuration management for DeploymentRuntime.

This module provides configuration classes and validation for DeploymentRuntime
using Pydantic for type validation and settings management.
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, HttpUrl
from enum import Enum
import logging

log = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Valid log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DeploymentRuntimeConfig(BaseModel):
    """Configuration for DeploymentRuntime client."""

    # Core connection settings
    endpoint_url: HttpUrl = Field(
        ..., description="Base URL of deployed DeploymentRuntime container"
    )
    api_key: Optional[str] = Field(
        None, description="RunPod API key for authentication"
    )

    # Request settings
    timeout: float = Field(300.0, gt=0, description="Request timeout in seconds")
    max_retries: int = Field(
        3, ge=0, description="Maximum number of retries for failed requests"
    )
    retry_delay: float = Field(
        1.0, gt=0, description="Base delay between retries in seconds"
    )

    # Session settings
    connection_pool_size: int = Field(10, gt=0, description="HTTP connection pool size")
    max_connections_per_host: int = Field(
        5, gt=0, description="Max connections per host"
    )

    # Logging settings
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
    enable_request_logging: bool = Field(
        False, description="Enable detailed request/response logging"
    )

    # Security settings
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    user_agent: str = Field(
        "tetra-rp-deployment-runtime/1.0", description="User agent for requests"
    )

    # Performance settings
    enable_compression: bool = Field(
        True, description="Enable request/response compression"
    )
    chunk_size: int = Field(
        8192, gt=0, description="Chunk size for streaming responses"
    )

    class Config:
        env_prefix = "DEPLOYMENT_RUNTIME_"
        case_sensitive = False

    @validator("api_key", pre=True, always=True)
    def validate_api_key(cls, v):
        """Load API key from environment if not provided."""
        if v is None:
            v = os.getenv("RUNPOD_API_KEY")
        return v

    @validator("endpoint_url", pre=True)
    def validate_endpoint_url(cls, v):
        """Ensure endpoint URL is properly formatted."""
        if isinstance(v, str):
            v = v.rstrip("/")
            if not v.startswith(("http://", "https://")):
                v = "https://" + v
        return v

    @classmethod
    def from_env(cls) -> "DeploymentRuntimeConfig":
        """Create configuration from environment variables."""
        return cls(
            endpoint_url=os.getenv(
                "DEPLOYMENT_RUNTIME_ENDPOINT_URL", "https://localhost:8000"
            ),
            api_key=os.getenv("RUNPOD_API_KEY"),
            timeout=float(os.getenv("DEPLOYMENT_RUNTIME_TIMEOUT", "300.0")),
            max_retries=int(os.getenv("DEPLOYMENT_RUNTIME_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("DEPLOYMENT_RUNTIME_RETRY_DELAY", "1.0")),
            log_level=LogLevel(os.getenv("DEPLOYMENT_RUNTIME_LOG_LEVEL", "INFO")),
            enable_request_logging=os.getenv(
                "DEPLOYMENT_RUNTIME_ENABLE_REQUEST_LOGGING", "false"
            ).lower()
            == "true",
            verify_ssl=os.getenv("DEPLOYMENT_RUNTIME_VERIFY_SSL", "true").lower()
            == "true",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()

    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.value),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        if self.enable_request_logging:
            # Enable more detailed logging for HTTP requests
            logging.getLogger("aiohttp").setLevel(logging.DEBUG)
            logging.getLogger(__name__.split(".")[0]).setLevel(logging.DEBUG)


class RemoteClassConfig(BaseModel):
    """Configuration for remote class execution."""

    dependencies: List[str] = Field(
        default_factory=list, description="Python packages to install"
    )
    system_dependencies: List[str] = Field(
        default_factory=list, description="System packages to install"
    )

    # Resource limits
    memory_limit: Optional[str] = Field(
        None, description="Memory limit (e.g., '2Gi', '512Mi')"
    )
    cpu_limit: Optional[str] = Field(None, description="CPU limit (e.g., '1000m', '2')")
    gpu_count: int = Field(0, ge=0, description="Number of GPUs required")

    # Execution settings
    execution_timeout: float = Field(
        600.0, gt=0, description="Maximum execution time in seconds"
    )
    enable_caching: bool = Field(True, description="Enable result caching")
    cache_ttl: int = Field(3600, ge=0, description="Cache TTL in seconds")

    @validator("dependencies")
    def validate_dependencies(cls, v):
        """Validate dependency format."""
        for dep in v:
            if not isinstance(dep, str) or not dep.strip():
                raise ValueError(f"Invalid dependency: {dep}")
        return v

    @validator("system_dependencies")
    def validate_system_dependencies(cls, v):
        """Validate system dependency format."""
        for dep in v:
            if not isinstance(dep, str) or not dep.strip():
                raise ValueError(f"Invalid system dependency: {dep}")
        return v


class EndpointConfig(BaseModel):
    """Configuration for HTTP endpoint methods."""

    methods: List[str] = Field(["POST"], description="Supported HTTP methods")
    route: Optional[str] = Field(None, description="Custom route path")

    # Request validation
    max_request_size: int = Field(
        10 * 1024 * 1024, gt=0, description="Maximum request size in bytes"
    )
    require_auth: bool = Field(True, description="Require authentication")

    # Rate limiting
    rate_limit: Optional[int] = Field(
        None, ge=1, description="Requests per minute limit"
    )

    @validator("methods")
    def validate_methods(cls, v):
        """Validate HTTP methods."""
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
        for method in v:
            if method.upper() not in valid_methods:
                raise ValueError(f"Invalid HTTP method: {method}")
        return [m.upper() for m in v]
