"""
Custom exceptions for DeploymentRuntime functionality.

This module defines specific exception types for different error conditions
that can occur during DeploymentRuntime operations.
"""

from typing import Optional, Dict, Any


class DeploymentRuntimeError(Exception):
    """Base exception for all DeploymentRuntime related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class DeploymentRuntimeConnectionError(DeploymentRuntimeError):
    """Raised when connection to DeploymentRuntime endpoint fails."""

    def __init__(
        self, endpoint_url: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.endpoint_url = endpoint_url
        super().__init__(f"Connection failed to {endpoint_url}: {message}", details)


class DeploymentRuntimeAuthenticationError(DeploymentRuntimeError):
    """Raised when authentication with DeploymentRuntime fails."""

    pass


class DeploymentRuntimeExecutionError(DeploymentRuntimeError):
    """Raised when remote execution fails."""

    def __init__(
        self, method_name: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.method_name = method_name
        super().__init__(f"Execution failed for {method_name}: {message}", details)


class DeploymentRuntimeSerializationError(DeploymentRuntimeError):
    """Raised when serialization/deserialization fails."""

    def __init__(
        self, operation: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        super().__init__(f"Serialization error during {operation}: {message}", details)


class DeploymentRuntimeTimeoutError(DeploymentRuntimeError):
    """Raised when an operation times out."""

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s", details
        )


class DeploymentRuntimeConfigurationError(DeploymentRuntimeError):
    """Raised when configuration is invalid."""

    pass


class DeploymentRuntimeValidationError(DeploymentRuntimeError):
    """Raised when input validation fails."""

    def __init__(
        self, field: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.field = field
        super().__init__(f"Validation error for {field}: {message}", details)
