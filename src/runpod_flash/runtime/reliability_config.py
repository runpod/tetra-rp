"""Centralized configuration for reliability features."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoadBalancerStrategy(Enum):
    """Load balancing strategies for endpoint selection."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    enabled: bool = True
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: int = 60
    window_size: int = 10


@dataclass
class LoadBalancerConfig:
    """Configuration for load balancer behavior."""

    enabled: bool = False
    strategy: LoadBalancerStrategy = LoadBalancerStrategy.ROUND_ROBIN


@dataclass
class RetryConfig:
    """Configuration for retry behavior with exponential backoff."""

    enabled: bool = True
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    jitter: float = 0.2
    retryable_exceptions: tuple = field(
        default_factory=lambda: (TimeoutError, ConnectionError)
    )
    retryable_status_codes: set = field(
        default_factory=lambda: {408, 429, 500, 502, 503, 504}
    )


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""

    enabled: bool = True
    namespace: str = "tetra.metrics"


@dataclass
class ReliabilityConfig:
    """Centralized reliability features configuration."""

    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    load_balancer: LoadBalancerConfig = field(default_factory=LoadBalancerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    @classmethod
    def from_env(cls) -> "ReliabilityConfig":
        """Load configuration from environment variables.

        Environment variables:
        - TETRA_CIRCUIT_BREAKER_ENABLED: Enable circuit breaker (default: true)
        - TETRA_CB_FAILURE_THRESHOLD: Failures before opening (default: 5)
        - TETRA_CB_SUCCESS_THRESHOLD: Successes to close (default: 2)
        - TETRA_CB_TIMEOUT_SECONDS: Time before half-open (default: 60)
        - TETRA_LOAD_BALANCER_ENABLED: Enable load balancer (default: false)
        - TETRA_LB_STRATEGY: Load balancer strategy (default: round_robin)
        - TETRA_RETRY_ENABLED: Enable retry (default: true)
        - TETRA_RETRY_MAX_ATTEMPTS: Max retry attempts (default: 3)
        - TETRA_RETRY_BASE_DELAY: Base delay for backoff (default: 0.5)
        - TETRA_METRICS_ENABLED: Enable metrics (default: true)

        Returns:
            ReliabilityConfig initialized from environment variables.
        """
        circuit_breaker = CircuitBreakerConfig(
            enabled=os.getenv("TETRA_CIRCUIT_BREAKER_ENABLED", "true").lower()
            == "true",
            failure_threshold=int(os.getenv("TETRA_CB_FAILURE_THRESHOLD", "5")),
            success_threshold=int(os.getenv("TETRA_CB_SUCCESS_THRESHOLD", "2")),
            timeout_seconds=int(os.getenv("TETRA_CB_TIMEOUT_SECONDS", "60")),
        )

        strategy_str = os.getenv("TETRA_LB_STRATEGY", "round_robin").lower()
        try:
            strategy = LoadBalancerStrategy(strategy_str)
        except ValueError:
            strategy = LoadBalancerStrategy.ROUND_ROBIN

        load_balancer = LoadBalancerConfig(
            enabled=os.getenv("TETRA_LOAD_BALANCER_ENABLED", "false").lower() == "true",
            strategy=strategy,
        )

        retry = RetryConfig(
            enabled=os.getenv("TETRA_RETRY_ENABLED", "true").lower() == "true",
            max_attempts=int(os.getenv("TETRA_RETRY_MAX_ATTEMPTS", "3")),
            base_delay=float(os.getenv("TETRA_RETRY_BASE_DELAY", "0.5")),
        )

        metrics = MetricsConfig(
            enabled=os.getenv("TETRA_METRICS_ENABLED", "true").lower() == "true",
        )

        return cls(
            circuit_breaker=circuit_breaker,
            load_balancer=load_balancer,
            retry=retry,
            metrics=metrics,
        )


# Global default configuration
_config: Optional[ReliabilityConfig] = None


def get_reliability_config() -> ReliabilityConfig:
    """Get global reliability configuration (lazy-loaded).

    Returns:
        ReliabilityConfig instance initialized from environment.
    """
    global _config
    if _config is None:
        _config = ReliabilityConfig.from_env()
    return _config


def set_reliability_config(config: ReliabilityConfig) -> None:
    """Set global reliability configuration (for testing).

    Args:
        config: ReliabilityConfig to set as global.
    """
    global _config
    _config = config
