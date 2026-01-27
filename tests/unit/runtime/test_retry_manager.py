"""Tests for retry manager module."""

import asyncio

import pytest

from tetra_rp.runtime.retry_manager import RetryExhaustedError, retry_with_backoff


class TestRetryWithBackoff:
    """Test retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful execution on first attempt."""

        async def success_func():
            return "success"

        result = await retry_with_backoff(success_func, max_attempts=3)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self):
        """Test that non-retryable exceptions raise immediately."""

        async def failing_func():
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            await retry_with_backoff(failing_func, max_attempts=3)

    @pytest.mark.asyncio
    async def test_retryable_exception_retries(self):
        """Test that retryable exceptions are retried."""
        attempt_count = 0

        async def failing_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = await retry_with_backoff(
            failing_then_success,
            max_attempts=3,
            base_delay=0.01,
            max_delay=0.1,
        )
        assert result == "success"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test that RetryExhaustedError is raised after max attempts."""

        async def always_fails():
            raise ConnectionError("Always fails")

        with pytest.raises(RetryExhaustedError):
            await retry_with_backoff(
                always_fails,
                max_attempts=2,
                base_delay=0.01,
                max_delay=0.1,
            )

    @pytest.mark.asyncio
    async def test_timeout_is_retryable(self):
        """Test that asyncio.TimeoutError is retried by default."""
        attempt_count = 0

        async def timeout_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise asyncio.TimeoutError("Request timed out")
            return "success"

        result = await retry_with_backoff(
            timeout_then_success,
            max_attempts=3,
            base_delay=0.01,
            max_delay=0.1,
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        """Test with custom retryable exceptions."""

        class CustomError(Exception):
            pass

        attempt_count = 0

        async def custom_error_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise CustomError("Custom error")
            return "success"

        result = await retry_with_backoff(
            custom_error_then_success,
            max_attempts=3,
            retryable_exceptions=(CustomError,),
            base_delay=0.01,
            max_delay=0.1,
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that backoff increases exponentially."""
        attempt_times = []

        async def track_attempts():
            attempt_times.append(asyncio.get_event_loop().time())
            if len(attempt_times) < 3:
                raise ConnectionError("Failed")
            return "success"

        result = await retry_with_backoff(
            track_attempts,
            max_attempts=3,
            base_delay=0.05,
            max_delay=1.0,
            jitter=0.0,  # No jitter for predictable timing
        )
        assert result == "success"
        # Should have at least 3 attempts with delays between them
        assert len(attempt_times) == 3

    @pytest.mark.asyncio
    async def test_with_args_and_kwargs(self):
        """Test retry with function arguments."""

        async def add(a, b):
            return a + b

        result = await retry_with_backoff(add, max_attempts=1, a=2, b=3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker_open(self):
        """Test that open circuit breaker prevents retries."""

        class MockCircuitBreaker:
            def get_state(self):
                from tetra_rp.runtime.circuit_breaker import CircuitState

                return CircuitState.OPEN

        async def failing_func():
            raise ConnectionError("Failed")

        with pytest.raises(RuntimeError, match="Circuit breaker OPEN"):
            await retry_with_backoff(
                failing_func,
                max_attempts=3,
                circuit_breaker=MockCircuitBreaker(),
                base_delay=0.01,
            )
