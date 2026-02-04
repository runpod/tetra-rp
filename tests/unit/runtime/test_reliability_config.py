"""Tests for reliability configuration module."""

from runpod_flash.runtime.reliability_config import (
    CircuitBreakerConfig,
    LoadBalancerConfig,
    LoadBalancerStrategy,
    MetricsConfig,
    ReliabilityConfig,
    RetryConfig,
    get_reliability_config,
)


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = CircuitBreakerConfig()
        assert config.enabled is True
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 60
        assert config.window_size == 10

    def test_custom_values(self):
        """Test with custom values."""
        config = CircuitBreakerConfig(
            enabled=False,
            failure_threshold=10,
            success_threshold=3,
            timeout_seconds=30,
            window_size=20,
        )
        assert config.enabled is False
        assert config.failure_threshold == 10
        assert config.success_threshold == 3
        assert config.timeout_seconds == 30
        assert config.window_size == 20


class TestLoadBalancerConfig:
    """Test LoadBalancerConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = LoadBalancerConfig()
        assert config.enabled is False
        assert config.strategy == LoadBalancerStrategy.ROUND_ROBIN

    def test_custom_values(self):
        """Test with custom values."""
        config = LoadBalancerConfig(
            enabled=True,
            strategy=LoadBalancerStrategy.LEAST_CONNECTIONS,
        )
        assert config.enabled is True
        assert config.strategy == LoadBalancerStrategy.LEAST_CONNECTIONS


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = RetryConfig()
        assert config.enabled is True
        assert config.max_attempts == 3
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.jitter == 0.2
        assert 408 in config.retryable_status_codes
        assert 500 in config.retryable_status_codes

    def test_custom_values(self):
        """Test with custom values."""
        config = RetryConfig(
            enabled=False,
            max_attempts=5,
            base_delay=1.0,
            max_delay=20.0,
            jitter=0.1,
        )
        assert config.enabled is False
        assert config.max_attempts == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 20.0
        assert config.jitter == 0.1


class TestMetricsConfig:
    """Test MetricsConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.namespace == "flash.metrics"

    def test_custom_values(self):
        """Test with custom values."""
        config = MetricsConfig(enabled=False, namespace="custom.metrics")
        assert config.enabled is False
        assert config.namespace == "custom.metrics"


class TestReliabilityConfig:
    """Test ReliabilityConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = ReliabilityConfig()
        assert config.circuit_breaker is not None
        assert config.load_balancer is not None
        assert config.retry is not None
        assert config.metrics is not None
        assert config.circuit_breaker.enabled is True
        assert config.load_balancer.enabled is False
        assert config.retry.enabled is True
        assert config.metrics.enabled is True

    def test_custom_nested_configs(self):
        """Test with custom nested configurations."""
        cb_config = CircuitBreakerConfig(enabled=False)
        lb_config = LoadBalancerConfig(enabled=True)
        config = ReliabilityConfig(
            circuit_breaker=cb_config,
            load_balancer=lb_config,
        )
        assert config.circuit_breaker.enabled is False
        assert config.load_balancer.enabled is True

    def test_from_env_default(self, monkeypatch):
        """Test from_env with no environment variables."""
        monkeypatch.delenv("FLASH_CIRCUIT_BREAKER_ENABLED", raising=False)
        config = ReliabilityConfig.from_env()
        assert config.circuit_breaker.enabled is True
        assert config.load_balancer.enabled is False
        assert config.retry.enabled is True

    def test_from_env_custom(self, monkeypatch):
        """Test from_env with custom environment variables."""
        monkeypatch.setenv("FLASH_CIRCUIT_BREAKER_ENABLED", "false")
        monkeypatch.setenv("FLASH_LOAD_BALANCER_ENABLED", "true")
        monkeypatch.setenv("FLASH_CB_FAILURE_THRESHOLD", "10")
        config = ReliabilityConfig.from_env()
        assert config.circuit_breaker.enabled is False
        assert config.load_balancer.enabled is True
        assert config.circuit_breaker.failure_threshold == 10

    def test_from_env_load_balancer_strategy(self, monkeypatch):
        """Test from_env with load balancer strategy."""
        monkeypatch.setenv("FLASH_LB_STRATEGY", "least_connections")
        config = ReliabilityConfig.from_env()
        assert config.load_balancer.strategy == LoadBalancerStrategy.LEAST_CONNECTIONS

    def test_from_env_invalid_strategy_defaults(self, monkeypatch):
        """Test from_env with invalid strategy defaults to round_robin."""
        monkeypatch.setenv("FLASH_LB_STRATEGY", "invalid_strategy")
        config = ReliabilityConfig.from_env()
        assert config.load_balancer.strategy == LoadBalancerStrategy.ROUND_ROBIN


class TestLoadBalancerStrategy:
    """Test LoadBalancerStrategy enum."""

    def test_strategy_values(self):
        """Test that strategies have correct values."""
        assert LoadBalancerStrategy.ROUND_ROBIN.value == "round_robin"
        assert LoadBalancerStrategy.LEAST_CONNECTIONS.value == "least_connections"
        assert LoadBalancerStrategy.RANDOM.value == "random"


class TestGlobalConfig:
    """Test global configuration accessor."""

    def test_get_reliability_config(self):
        """Test getting global reliability config."""
        config = get_reliability_config()
        assert isinstance(config, ReliabilityConfig)
        assert config.circuit_breaker is not None
