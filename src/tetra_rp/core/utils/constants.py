"""
Constants for utility modules and caching configurations.

This module contains configurable constants used across the tetra-rp codebase
to ensure consistency and easy maintenance.
"""

# Cache key generation constants
HASH_TRUNCATE_LENGTH = 16  # Length to truncate hash values for cache keys
UUID_FALLBACK_LENGTH = 8  # Length to truncate UUID values for fallback keys
