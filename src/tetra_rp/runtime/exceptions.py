"""Custom exceptions for cross-endpoint runtime."""


class RuntimeError(Exception):
    """Base exception for runtime errors in cross-endpoint execution."""

    pass


class RemoteExecutionError(RuntimeError):
    """Raised when remote function execution fails."""

    pass


class SerializationError(RuntimeError):
    """Raised when serialization or deserialization of arguments fails."""

    pass


class ManifestError(RuntimeError):
    """Raised when manifest is invalid, missing, or has unexpected structure."""

    pass


class DirectoryUnavailableError(RuntimeError):
    """Raised when directory service is unavailable."""

    pass
