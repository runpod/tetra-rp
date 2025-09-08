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


class LoadBalancerSlsConfigurationError(LoadBalancerSlsError):
    """Raised when configuration is invalid."""

    pass
