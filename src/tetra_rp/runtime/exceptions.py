"""Custom exceptions for cross-endpoint runtime."""


class FlashRuntimeError(Exception):
    """Base exception for runtime errors in cross-endpoint execution."""

    pass


class RemoteExecutionError(FlashRuntimeError):
    """Raised when remote function execution fails."""

    pass


class SerializationError(FlashRuntimeError):
    """Raised when serialization or deserialization of arguments fails."""

    pass


class ManifestError(FlashRuntimeError):
    """Raised when manifest is invalid, missing, or has unexpected structure."""

    pass


class ManifestServiceUnavailableError(FlashRuntimeError):
    """Raised when manifest directory service is unavailable."""

    pass
