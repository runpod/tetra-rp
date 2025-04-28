from enum import Enum
from typing import Any
from pydantic import BaseModel


def normalize_for_json(obj: Any) -> Any:
    """
    Recursively normalizes an object for JSON serialization.

    This function handles various data types and ensures that objects
    are converted into JSON-serializable formats. It supports the following:
    - `BaseModel` instances: Converts them to dictionaries using `model_dump()`.
    - Dictionaries: Recursively normalizes their values.
    - Lists: Recursively normalizes their elements.
    - Tuples: Recursively normalizes their elements and returns a tuple.
    - Other types: Returns the object as is.

    Args:
        obj (Any): The object to normalize.

    Returns:
        Any: A JSON-serializable representation of the input object.
    """
    if isinstance(obj, BaseModel):
        return normalize_for_json(obj.model_dump())
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: normalize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(normalize_for_json(i) for i in obj)
    else:
        return obj
