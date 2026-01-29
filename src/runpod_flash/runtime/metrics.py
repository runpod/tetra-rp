"""Metrics collection via structured logging for observability."""

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """Representation of a single metric."""

    metric_type: MetricType
    metric_name: str
    value: float
    labels: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary.

        Returns:
            Dictionary representation of metric
        """
        return asdict(self)


class MetricsCollector:
    """Collect metrics via structured logging."""

    def __init__(self, namespace: str = "tetra.metrics", enabled: bool = True):
        """Initialize metrics collector.

        Args:
            namespace: Namespace for metrics (used in structured logging)
            enabled: Whether metrics collection is enabled
        """
        self.namespace = namespace
        self.enabled = enabled

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a counter metric (cumulative).

        Args:
            name: Name of the metric
            value: Value to add to counter (default: 1.0)
            labels: Optional labels/tags for the metric
        """
        if not self.enabled:
            return

        metric = Metric(MetricType.COUNTER, name, value, labels or {})
        self._emit(metric)

    def gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a gauge metric (point-in-time value).

        Args:
            name: Name of the metric
            value: Current value of the gauge
            labels: Optional labels/tags for the metric
        """
        if not self.enabled:
            return

        metric = Metric(MetricType.GAUGE, name, value, labels or {})
        self._emit(metric)

    def histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a histogram metric (distribution).

        Args:
            name: Name of the metric
            value: Value to add to histogram
            labels: Optional labels/tags for the metric
        """
        if not self.enabled:
            return

        metric = Metric(MetricType.HISTOGRAM, name, value, labels or {})
        self._emit(metric)

    def _emit(self, metric: Metric) -> None:
        """Emit metric via structured logging.

        Args:
            metric: Metric to emit
        """
        try:
            logger.info(
                f"[METRIC] {metric.metric_name}={metric.value}",
                extra={
                    "namespace": self.namespace,
                    "metric": metric.to_dict(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to emit metric {metric.metric_name}: {e}")


# Global metrics collector instance
_collector: Optional[MetricsCollector] = None


def get_metrics_collector(
    namespace: str = "tetra.metrics", enabled: bool = True
) -> MetricsCollector:
    """Get global metrics collector (lazy-loaded).

    Args:
        namespace: Namespace for metrics
        enabled: Whether metrics collection is enabled

    Returns:
        MetricsCollector instance
    """
    global _collector
    if _collector is None:
        _collector = MetricsCollector(namespace=namespace, enabled=enabled)
    return _collector


def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set global metrics collector (for testing).

    Args:
        collector: MetricsCollector instance
    """
    global _collector
    _collector = collector


class CircuitBreakerMetrics:
    """Helper for emitting circuit breaker metrics."""

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """Initialize circuit breaker metrics helper.

        Args:
            collector: Optional MetricsCollector instance (uses global if not provided)
        """
        self.collector = collector or get_metrics_collector()

    def state_changed(
        self, endpoint_url: str, new_state: str, previous_state: str
    ) -> None:
        """Emit metric when circuit breaker state changes.

        Args:
            endpoint_url: URL of the endpoint
            new_state: New circuit state
            previous_state: Previous circuit state
        """
        self.collector.counter(
            "circuit_breaker_state_changes",
            value=1.0,
            labels={
                "endpoint_url": endpoint_url,
                "new_state": new_state,
                "previous_state": previous_state,
            },
        )

    def endpoint_requests(self, endpoint_url: str, status: str, count: int = 1) -> None:
        """Emit metric for endpoint requests.

        Args:
            endpoint_url: URL of the endpoint
            status: Request status (success, failure, etc.)
            count: Number of requests
        """
        self.collector.counter(
            "endpoint_requests",
            value=float(count),
            labels={"endpoint_url": endpoint_url, "status": status},
        )

    def endpoint_latency(self, endpoint_url: str, latency_ms: float) -> None:
        """Emit metric for endpoint latency.

        Args:
            endpoint_url: URL of the endpoint
            latency_ms: Latency in milliseconds
        """
        self.collector.histogram(
            "endpoint_latency",
            value=latency_ms,
            labels={"endpoint_url": endpoint_url},
        )

    def in_flight_requests(self, endpoint_url: str, count: int) -> None:
        """Emit metric for in-flight requests.

        Args:
            endpoint_url: URL of the endpoint
            count: Current number of in-flight requests
        """
        self.collector.gauge(
            "in_flight_requests",
            value=float(count),
            labels={"endpoint_url": endpoint_url},
        )


class RetryMetrics:
    """Helper for emitting retry metrics."""

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """Initialize retry metrics helper.

        Args:
            collector: Optional MetricsCollector instance (uses global if not provided)
        """
        self.collector = collector or get_metrics_collector()

    def retry_attempt(
        self, function_name: str, attempt: int, error: Optional[str] = None
    ) -> None:
        """Emit metric for retry attempt.

        Args:
            function_name: Name of the function being retried
            attempt: Attempt number
            error: Optional error message
        """
        labels = {
            "function_name": function_name,
            "attempt": str(attempt),
        }
        if error:
            labels["error"] = error

        self.collector.counter(
            "retry_attempts",
            value=1.0,
            labels=labels,
        )

    def retry_success(self, function_name: str, total_attempts: int) -> None:
        """Emit metric for successful retry.

        Args:
            function_name: Name of the function
            total_attempts: Total attempts made before success
        """
        self.collector.counter(
            "retry_success",
            value=1.0,
            labels={
                "function_name": function_name,
                "attempts": str(total_attempts),
            },
        )

    def retry_exhausted(self, function_name: str, max_attempts: int) -> None:
        """Emit metric when max retries exceeded.

        Args:
            function_name: Name of the function
            max_attempts: Maximum attempts configured
        """
        self.collector.counter(
            "retry_exhausted",
            value=1.0,
            labels={
                "function_name": function_name,
                "max_attempts": str(max_attempts),
            },
        )


class LoadBalancerMetrics:
    """Helper for emitting load balancer metrics."""

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """Initialize load balancer metrics helper.

        Args:
            collector: Optional MetricsCollector instance (uses global if not provided)
        """
        self.collector = collector or get_metrics_collector()

    def endpoint_selected(
        self, strategy: str, endpoint_url: str, total_candidates: int
    ) -> None:
        """Emit metric when endpoint is selected.

        Args:
            strategy: Load balancing strategy used
            endpoint_url: Selected endpoint URL
            total_candidates: Total candidate endpoints
        """
        self.collector.counter(
            "load_balancer_selection",
            value=1.0,
            labels={
                "strategy": strategy,
                "endpoint_url": endpoint_url,
                "candidates": str(total_candidates),
            },
        )
