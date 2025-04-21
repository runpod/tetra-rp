import math
import random
from enum import Enum


class BackoffStrategy(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"


def get_backoff_delay(
    attempt: int,
    base: float = 0.1,
    max_seconds: float = 10.0,
    jitter: float = 0.2,
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
) -> float:
    """
    Returns a backoff delay in seconds based on the number of attempts and strategy.

    Parameters:
    - attempt (int): The number of failed attempts or polls.
    - base (float): The base delay time in seconds.
    - max_seconds (float): The maximum delay.
    - jitter (float): Random jitter as a fraction (e.g., 0.2 = ±20%). Prevent thundering herd
    - strategy (BackoffStrategy): The backoff curve to apply.

    Returns:
    - float: The delay in seconds.
    """
    if strategy == BackoffStrategy.EXPONENTIAL:
        delay = base * (2**attempt)
    elif strategy == BackoffStrategy.LINEAR:
        delay = base + (attempt * base)
    elif strategy == BackoffStrategy.LOGARITHMIC:
        delay = base * math.log2(attempt + 2)
    else:
        raise ValueError(f"Unsupported backoff strategy: {strategy}")

    # Clamp to max and apply jitter
    delay = min(delay, max_seconds)
    return delay * random.uniform(1 - jitter, 1 + jitter)
