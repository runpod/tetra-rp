"""
LoadBalancerSls Package

This package provides LoadBalancerSls functionality for dual-capability remote execution,
supporting both HTTP endpoints and remote execution through a unified interface.
"""

from .client import LoadBalancerSls
from .endpoint import endpoint
from .exceptions import (
    LoadBalancerSlsError,
    LoadBalancerSlsConnectionError,
    LoadBalancerSlsAuthenticationError,
    LoadBalancerSlsExecutionError,
    LoadBalancerSlsConfigurationError,
)

__all__ = [
    "LoadBalancerSls",
    "endpoint",
    "LoadBalancerSlsError",
    "LoadBalancerSlsConnectionError",
    "LoadBalancerSlsAuthenticationError",
    "LoadBalancerSlsExecutionError",
    "LoadBalancerSlsConfigurationError",
]
