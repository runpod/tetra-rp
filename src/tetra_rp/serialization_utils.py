import base64
import cloudpickle
from typing import Any, List, Dict


class SerializationUtils:
    """Utilities for serializing and deserializing function arguments and results."""

    @staticmethod
    def serialize_result(result: Any) -> str:
        """Serialize a result using cloudpickle and base64 encoding."""
        return base64.b64encode(cloudpickle.dumps(result)).decode("utf-8")

    @staticmethod
    def deserialize_result(encoded_result: str) -> Any:
        """Deserialize a result from base64-encoded cloudpickle."""
        return cloudpickle.loads(base64.b64decode(encoded_result))

    @staticmethod
    def deserialize_args(args: List[str]) -> List[Any]:
        """Deserialize function arguments from base64-encoded cloudpickle."""
        return [cloudpickle.loads(base64.b64decode(arg)) for arg in args]

    @staticmethod
    def deserialize_kwargs(kwargs: Dict[str, str]) -> Dict[str, Any]:
        """Deserialize function keyword arguments from base64-encoded cloudpickle."""
        return {k: cloudpickle.loads(base64.b64decode(v)) for k, v in kwargs.items()}