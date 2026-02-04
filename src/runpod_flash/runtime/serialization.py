"""Shared serialization utilities for cloudpickle + base64 encoding."""

import base64
from typing import Any, Dict, List

import cloudpickle

from .exceptions import SerializationError


def serialize_arg(arg: Any) -> str:
    """Serialize single argument with cloudpickle + base64.

    Args:
        arg: Argument to serialize.

    Returns:
        Base64-encoded cloudpickle serialized string.

    Raises:
        SerializationError: If serialization fails.
    """
    try:
        return base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8")
    except Exception as e:
        raise SerializationError(f"Failed to serialize argument: {e}") from e


def serialize_args(args: tuple) -> List[str]:
    """Serialize positional arguments.

    Args:
        args: Tuple of arguments to serialize.

    Returns:
        List of base64-encoded serialized arguments.

    Raises:
        SerializationError: If serialization fails.
    """
    try:
        return [serialize_arg(arg) for arg in args]
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to serialize args: {e}") from e


def serialize_kwargs(kwargs: dict) -> Dict[str, str]:
    """Serialize keyword arguments.

    Args:
        kwargs: Dictionary of keyword arguments.

    Returns:
        Dictionary with base64-encoded serialized values.

    Raises:
        SerializationError: If serialization fails.
    """
    try:
        return {k: serialize_arg(v) for k, v in kwargs.items()}
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to serialize kwargs: {e}") from e


def deserialize_arg(arg_b64: str) -> Any:
    """Deserialize single base64-encoded cloudpickle argument.

    Args:
        arg_b64: Base64-encoded serialized argument.

    Returns:
        Deserialized argument.

    Raises:
        SerializationError: If deserialization fails.
    """
    try:
        return cloudpickle.loads(base64.b64decode(arg_b64))
    except Exception as e:
        raise SerializationError(f"Failed to deserialize argument: {e}") from e


def deserialize_args(args_b64: List[str]) -> List[Any]:
    """Deserialize list of base64-encoded arguments.

    Args:
        args_b64: List of base64-encoded serialized arguments.

    Returns:
        List of deserialized arguments.

    Raises:
        SerializationError: If deserialization fails.
    """
    try:
        return [deserialize_arg(arg) for arg in args_b64]
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to deserialize args: {e}") from e


def deserialize_kwargs(kwargs_b64: Dict[str, str]) -> Dict[str, Any]:
    """Deserialize dict of base64-encoded keyword arguments.

    Args:
        kwargs_b64: Dictionary with base64-encoded serialized values.

    Returns:
        Dictionary with deserialized values.

    Raises:
        SerializationError: If deserialization fails.
    """
    try:
        return {k: deserialize_arg(v) for k, v in kwargs_b64.items()}
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to deserialize kwargs: {e}") from e
