"""Utilities for normalizing data structures for JSON serialization."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


def normalize_for_json(obj: Any) -> Any:
    """Normalize an object for JSON serialization.

    Converts Pydantic models to dicts and Enum values to their values,
    while recursively processing collections.

    Args:
        obj: The object to normalize.

    Returns:
        A JSON-serializable version of the object.
    """
    # Handle primitives
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # Handle Enum
    if isinstance(obj, Enum):
        return obj.value

    # Handle Pydantic BaseModel
    if isinstance(obj, BaseModel):
        return normalize_for_json(obj.model_dump())

    # Handle dict
    if isinstance(obj, dict):
        return {key: normalize_for_json(value) for key, value in obj.items()}

    # Handle tuple
    if isinstance(obj, tuple):
        return tuple(normalize_for_json(item) for item in obj)

    # Handle list
    if isinstance(obj, list):
        return [normalize_for_json(item) for item in obj]

    # For any other type, return as-is
    return obj
