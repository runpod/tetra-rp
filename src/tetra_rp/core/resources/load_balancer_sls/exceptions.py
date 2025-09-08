"""
Custom exceptions for LoadBalancerSls functionality.

This module defines specific exception types for different error conditions
that can occur during LoadBalancerSls operations.
"""

from typing import Optional, Dict, Any


class LoadBalancerSlsError(Exception):
    """Base exception for all LoadBalancerSls related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class LoadBalancerSlsConnectionError(LoadBalancerSlsError):
    """Raised when connection to LoadBalancerSls endpoint fails."""

    def __init__(
        self, endpoint_url: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.endpoint_url = endpoint_url
        super().__init__(f"Connection failed to {endpoint_url}: {message}", details)


class LoadBalancerSlsAuthenticationError(LoadBalancerSlsError):
    """Raised when authentication with LoadBalancerSls fails."""

    pass


class LoadBalancerSlsExecutionError(LoadBalancerSlsError):
    """Raised when remote execution fails."""

    def __init__(
        self, method_name: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.method_name = method_name
        super().__init__(f"Execution failed for {method_name}: {message}", details)


class LoadBalancerSlsSerializationError(LoadBalancerSlsError):
    """Raised when serialization/deserialization fails."""

    def __init__(
        self, operation: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        super().__init__(f"Serialization error during {operation}: {message}", details)


class LoadBalancerSlsTimeoutError(LoadBalancerSlsError):
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


class LoadBalancerSlsConfigurationError(LoadBalancerSlsError):
    """Raised when configuration is invalid."""

    pass


class LoadBalancerSlsValidationError(LoadBalancerSlsError):
    """Raised when input validation fails."""

    def __init__(
        self, field: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        self.field = field
        super().__init__(f"Validation error for {field}: {message}", details)
