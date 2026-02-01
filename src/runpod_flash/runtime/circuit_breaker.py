"""Circuit breaker pattern for handling endpoint failures."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker state machine."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker instance."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    state_changed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_requests: int = 0
    total_failures: int = 0


class EndpointCircuitBreaker:
    """Circuit breaker for a single endpoint with sliding window."""

    def __init__(
        self,
        endpoint_url: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
        window_size: int = 10,
    ):
        """Initialize circuit breaker for an endpoint.

        Args:
            endpoint_url: URL of the endpoint to protect
            failure_threshold: Failures required to open circuit
            success_threshold: Successes required to close circuit
            timeout_seconds: Time before attempting recovery
            window_size: Size of sliding window for counting failures
        """
        self.endpoint_url = endpoint_url
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.window_size = window_size
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._failure_times: list[float] = []

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        async with self._lock:
            state = self.stats.state

            if state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit OPEN for {self.endpoint_url}. "
                        f"Retry in {self._seconds_until_recovery()}s"
                    )

        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self) -> None:
        """Record successful request."""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.total_requests += 1
            self.stats.last_success_at = datetime.now(timezone.utc)

            logger.debug(
                f"Circuit breaker {self.endpoint_url}: "
                f"success {self.stats.success_count}/{self.success_threshold}"
            )

            if self.stats.state == CircuitState.HALF_OPEN:
                # Close circuit after successes
                if self.stats.success_count >= self.success_threshold:
                    self._transition_to_closed()
            elif self.stats.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.stats.failure_count = 0
                self._failure_times.clear()

    async def _on_failure(self, error: Exception) -> None:
        """Record failed request."""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.total_requests += 1
            self.stats.last_failure_at = datetime.now(timezone.utc)

            # Track failure times for sliding window
            now = time.time()
            self._failure_times.append(now)

            # Keep only failures within window
            cutoff = now - self.timeout_seconds
            self._failure_times = [t for t in self._failure_times if t > cutoff]

            logger.debug(
                f"Circuit breaker {self.endpoint_url}: "
                f"failure {self.stats.failure_count}/{self.failure_threshold}, "
                f"error: {error}"
            )

            if self.stats.state == CircuitState.HALF_OPEN:
                # Open circuit on first failure in half-open
                self._transition_to_open()
            elif self.stats.state == CircuitState.CLOSED:
                # Open circuit if threshold reached
                if len(self._failure_times) >= self.failure_threshold:
                    self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        if self.stats.state == CircuitState.OPEN:
            return  # Already open
        self.stats.state = CircuitState.OPEN
        self.stats.state_changed_at = datetime.now(timezone.utc)
        self.stats.success_count = 0
        logger.warning(
            f"Circuit breaker OPEN for {self.endpoint_url} "
            f"after {self.stats.failure_count} failures"
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.state_changed_at = datetime.now(timezone.utc)
        self.stats.failure_count = 0
        self.stats.success_count = 0
        logger.info(
            f"Circuit breaker HALF_OPEN for {self.endpoint_url}, testing recovery"
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self.stats.state = CircuitState.CLOSED
        self.stats.state_changed_at = datetime.now(timezone.utc)
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self._failure_times.clear()
        logger.info(f"Circuit breaker CLOSED for {self.endpoint_url}, recovered")

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self.stats.last_failure_at:
            return False
        elapsed = datetime.now(timezone.utc) - self.stats.state_changed_at
        return elapsed.total_seconds() >= self.timeout_seconds

    def _seconds_until_recovery(self) -> int:
        """Get seconds until recovery can be attempted."""
        if not self.stats.state_changed_at:
            return self.timeout_seconds
        elapsed = datetime.now(timezone.utc) - self.stats.state_changed_at
        remaining = self.timeout_seconds - int(elapsed.total_seconds())
        return max(0, remaining)

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.stats.state

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats


class CircuitBreakerRegistry:
    """Manages circuit breakers for multiple endpoints."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
    ):
        """Initialize circuit breaker registry.

        Args:
            failure_threshold: Failures required to open circuit
            success_threshold: Successes required to close circuit
            timeout_seconds: Time before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self._breakers: dict[str, EndpointCircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_breaker(self, endpoint_url: str) -> EndpointCircuitBreaker:
        """Get or create circuit breaker for endpoint.

        Args:
            endpoint_url: URL of the endpoint

        Returns:
            EndpointCircuitBreaker instance
        """
        if endpoint_url not in self._breakers:
            self._breakers[endpoint_url] = EndpointCircuitBreaker(
                endpoint_url,
                failure_threshold=self.failure_threshold,
                success_threshold=self.success_threshold,
                timeout_seconds=self.timeout_seconds,
            )
        return self._breakers[endpoint_url]

    def get_state(self, endpoint_url: str) -> CircuitState:
        """Get state of circuit breaker for endpoint.

        Args:
            endpoint_url: URL of the endpoint

        Returns:
            Current circuit state
        """
        breaker = self.get_breaker(endpoint_url)
        return breaker.get_state()

    def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers.

        Returns:
            Mapping of endpoint URLs to statistics
        """
        return {url: breaker.get_stats() for url, breaker in self._breakers.items()}


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass
