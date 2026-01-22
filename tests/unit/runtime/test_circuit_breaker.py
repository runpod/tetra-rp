"""Tests for circuit breaker module."""

import asyncio

import pytest

from tetra_rp.runtime.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitState,
    EndpointCircuitBreaker,
)


class TestCircuitState:
    """Test CircuitState enum."""

    def test_states(self):
        """Test circuit states exist."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestEndpointCircuitBreaker:
    """Test EndpointCircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful function execution."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=5,
            timeout_seconds=60,
        )

        async def success_func():
            return "success"

        result = await breaker.execute(success_func)
        assert result == "success"
        assert breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failed_execution_within_threshold(self):
        """Test failed execution within threshold."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=5,
            timeout_seconds=60,
        )

        async def failing_func():
            raise ConnectionError("Connection failed")

        for _ in range(4):  # 4 failures, threshold is 5
            with pytest.raises(ConnectionError):
                await breaker.execute(failing_func)
            assert breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_at_threshold(self):
        """Test circuit opens when failure threshold reached."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=3,
            timeout_seconds=60,
        )

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Reach threshold
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.execute(failing_func)

        # Circuit should be OPEN now
        assert breaker.get_state() == CircuitState.OPEN

        # Further requests should fail immediately
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.execute(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=2,
            timeout_seconds=1,
        )

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.execute(failing_func)

        assert breaker.get_state() == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Next attempt should transition to HALF_OPEN
        async def success_func():
            return "recovered"

        await breaker.execute(success_func)
        # First success in HALF_OPEN doesn't close circuit yet
        assert breaker.get_state() == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_threshold(self):
        """Test circuit closes after enough successes."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=1,
        )

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.execute(failing_func)

        assert breaker.get_state() == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Succeed enough times to close circuit
        async def success_func():
            return "success"

        for _ in range(2):
            result = await breaker.execute(success_func)
            assert result == "success"

        assert breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting circuit breaker statistics."""
        breaker = EndpointCircuitBreaker("http://example.com")

        async def success_func():
            return "ok"

        await breaker.execute(success_func)
        stats = breaker.get_stats()
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.state == CircuitState.CLOSED
        assert stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_half_open_resets_on_failure(self):
        """Test that failure in HALF_OPEN opens circuit again."""
        breaker = EndpointCircuitBreaker(
            "http://example.com",
            failure_threshold=1,
            timeout_seconds=1,
        )

        async def failing_func():
            raise ConnectionError("Connection failed")

        # Open circuit
        with pytest.raises(ConnectionError):
            await breaker.execute(failing_func)

        assert breaker.get_state() == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Attempt recovery, should transition to HALF_OPEN
        with pytest.raises(ConnectionError):
            await breaker.execute(failing_func)

        # Should transition back to OPEN on first failure
        assert breaker.get_state() == CircuitState.OPEN
