import base64
import cloudpickle
from typing import Any, List, Dict
import logging

log = logging.getLogger(__name__)


class SerializationUtils:
    """Utilities for serializing and deserializing function arguments and results.

    This class provides static methods for safe serialization/deserialization
    using cloudpickle and base64 encoding.
    """

    @staticmethod
    def serialize_result(result: Any) -> str:
        """Serialize a result using cloudpickle and base64 encoding.

        Args:
            result: The object to serialize

        Returns:
            Base64-encoded string representation of the serialized object

        Raises:
            SerializationError: If serialization fails
        """
        try:
            pickled_data = cloudpickle.dumps(result)
            return base64.b64encode(pickled_data).decode("utf-8")
        except Exception as e:
            from .exceptions import DeploymentRuntimeError

            log.error(f"Failed to serialize result: {e}")
            raise DeploymentRuntimeError(
                f"Serialization failed: {e}",
                {"error_type": type(e).__name__, "result_type": type(result).__name__},
            )

    @staticmethod
    def deserialize_result(encoded_result: str) -> Any:
        """Deserialize a result from base64-encoded cloudpickle.

        Args:
            encoded_result: Base64-encoded string to deserialize

        Returns:
            The deserialized object

        Raises:
            SerializationError: If deserialization fails
            TypeError: If encoded_result is not a string
        """
        if not isinstance(encoded_result, str):
            raise TypeError(
                f"encoded_result must be a string, got {type(encoded_result)}"
            )

        try:
            decoded_data = base64.b64decode(encoded_result)
            return cloudpickle.loads(decoded_data)
        except Exception as e:
            from .exceptions import DeploymentRuntimeError

            log.error(f"Failed to deserialize result: {e}")
            raise DeploymentRuntimeError(
                f"Deserialization failed: {e}",
                {"error_type": type(e).__name__, "encoded_length": len(encoded_result)},
            )

    @staticmethod
    def deserialize_args(args: List[str]) -> List[Any]:
        """Deserialize function arguments from base64-encoded cloudpickle.

        Args:
            args: List of base64-encoded strings to deserialize

        Returns:
            List of deserialized objects

        Raises:
            SerializationError: If deserialization fails
            TypeError: If args is not a list or contains non-strings
        """
        if not isinstance(args, list):
            raise TypeError(f"args must be a list, got {type(args)}")

        try:
            result = []
            for i, arg in enumerate(args):
                if not isinstance(arg, str):
                    raise TypeError(f"args[{i}] must be a string, got {type(arg)}")
                result.append(SerializationUtils.deserialize_result(arg))
            return result
        except Exception as e:
            from .exceptions import DeploymentRuntimeError

            if isinstance(e, DeploymentRuntimeError):
                raise
            log.error(f"Failed to deserialize args: {e}")
            raise DeploymentRuntimeError(
                f"Failed to deserialize function arguments: {e}",
                {"error_type": type(e).__name__, "args_count": len(args)},
            )

    @staticmethod
    def deserialize_kwargs(kwargs: Dict[str, str]) -> Dict[str, Any]:
        """Deserialize function keyword arguments from base64-encoded cloudpickle.

        Args:
            kwargs: Dict mapping parameter names to base64-encoded strings

        Returns:
            Dict mapping parameter names to deserialized objects

        Raises:
            SerializationError: If deserialization fails
            TypeError: If kwargs is not a dict or contains invalid types
        """
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dict, got {type(kwargs)}")

        try:
            result = {}
            for key, value in kwargs.items():
                if not isinstance(key, str):
                    raise TypeError(
                        f"kwargs key '{key}' must be a string, got {type(key)}"
                    )
                if not isinstance(value, str):
                    raise TypeError(
                        f"kwargs value for '{key}' must be a string, got {type(value)}"
                    )
                result[key] = SerializationUtils.deserialize_result(value)
            return result
        except Exception as e:
            from .exceptions import DeploymentRuntimeError

            if isinstance(e, DeploymentRuntimeError):
                raise
            log.error(f"Failed to deserialize kwargs: {e}")
            raise DeploymentRuntimeError(
                f"Failed to deserialize keyword arguments: {e}",
                {"error_type": type(e).__name__, "kwargs_keys": list(kwargs.keys())},
            )
