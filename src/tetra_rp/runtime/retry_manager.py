"""Retry logic with exponential backoff for failed remote calls."""

import asyncio
import logging
from typing import Any, Callable, Optional, Set, Tuple, Type

from tetra_rp.core.utils.backoff import get_backoff_delay

logger = logging.getLogger(__name__)


class RetryExhaustedError(Exception):
    """Raised when max retry attempts are exceeded."""

    pass


async def retry_with_backoff(
    func: Callable[..., Any],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: float = 0.2,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    retryable_status_codes: Optional[Set[int]] = None,
    circuit_breaker: Optional[Any] = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute async function with retry and exponential backoff.

    Args:
        func: Async function to execute
        max_attempts: Maximum number of attempts (default: 3)
        base_delay: Base delay between retries in seconds (default: 0.5)
        max_delay: Maximum delay between retries (default: 10.0)
        jitter: Jitter factor (0.0-1.0) to add randomness (default: 0.2)
        retryable_exceptions: Tuple of exception types to retry on
            (default: (asyncio.TimeoutError, ConnectionError))
        retryable_status_codes: Set of HTTP status codes to retry on
            (default: {408, 429, 500, 502, 503, 504})
        circuit_breaker: Optional circuit breaker to check before retry
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        RetryExhaustedError: If max attempts exceeded
        Exception: If non-retryable exception occurs
    """
    if retryable_exceptions is None:
        retryable_exceptions = (asyncio.TimeoutError, ConnectionError)

    if retryable_status_codes is None:
        retryable_status_codes = {408, 429, 500, 502, 503, 504}

    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            # Check circuit breaker before attempting
            if circuit_breaker is not None:
                from tetra_rp.runtime.circuit_breaker import CircuitState

                if circuit_breaker.get_state() == CircuitState.OPEN:
                    raise RuntimeError(
                        f"Circuit breaker OPEN, skipping retry attempt {attempt + 1}"
                    )

            result = await func(*args, **kwargs)

            # Log success on retry
            if attempt > 0:
                logger.info(f"Retry succeeded on attempt {attempt + 1}/{max_attempts}")

            return result

        except Exception as e:
            last_exception = e

            # Check if exception is retryable
            if not isinstance(e, retryable_exceptions):
                logger.debug(
                    f"Non-retryable exception in {func.__name__}: {type(e).__name__}"
                )
                raise

            # Check for retryable status codes (if exception has status_code)
            if hasattr(e, "status_code"):
                if e.status_code not in retryable_status_codes:  # type: ignore
                    logger.debug(
                        f"Non-retryable status code {e.status_code} in {func.__name__}"
                    )
                    raise

            # If this is the last attempt, don't retry
            if attempt >= max_attempts - 1:
                logger.warning(
                    f"Max retries ({max_attempts}) exhausted for {func.__name__}"
                )
                raise RetryExhaustedError(
                    f"Failed after {max_attempts} attempts: {e}"
                ) from e

            # Calculate delay with exponential backoff and jitter
            delay = get_backoff_delay(attempt, base_delay, max_delay, jitter=jitter)
            logger.debug(
                f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                f"after {delay:.2f}s"
            )
            await asyncio.sleep(delay)

    # Should never reach here, but handle edge case
    if last_exception:
        raise last_exception
    raise RetryExhaustedError(f"Failed after {max_attempts} attempts")
