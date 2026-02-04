"""Configuration constants for runtime module."""

# HTTP client configuration
DEFAULT_REQUEST_TIMEOUT = 10  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2

# Manifest cache configuration
DEFAULT_CACHE_TTL = 300  # seconds

# Serialization limits
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB
