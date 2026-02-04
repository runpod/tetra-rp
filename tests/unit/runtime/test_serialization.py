"""Tests for serialization utilities."""

from unittest.mock import patch

import pytest

from runpod_flash.runtime.exceptions import SerializationError
from runpod_flash.runtime.serialization import (
    deserialize_arg,
    deserialize_args,
    deserialize_kwargs,
    serialize_arg,
    serialize_args,
    serialize_kwargs,
)


class TestSerializeArg:
    """Test serialize_arg function."""

    def test_serialize_simple_arg(self):
        """Test serializing a simple argument."""
        result = serialize_arg(42)
        assert isinstance(result, str)
        # Verify it's valid base64
        import base64

        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_serialize_raises_on_cloudpickle_error(self):
        """Test serialize_arg handles cloudpickle errors."""
        with patch("cloudpickle.dumps") as mock_dumps:
            mock_dumps.side_effect = RuntimeError("Unexpected cloudpickle error")
            with pytest.raises(
                SerializationError, match="Failed to serialize argument"
            ):
                serialize_arg(42)


class TestSerializeArgs:
    """Test serialize_args function."""

    def test_serialize_multiple_args(self):
        """Test serializing multiple arguments."""
        result = serialize_args((1, "test", [1, 2, 3]))
        assert len(result) == 3
        assert all(isinstance(item, str) for item in result)

    def test_serialize_empty_args(self):
        """Test serializing empty args tuple."""
        result = serialize_args(())
        assert result == []

    def test_serialize_args_propagates_serialization_error(self):
        """Test serialize_args propagates SerializationError."""
        with patch(
            "runpod_flash.runtime.serialization.serialize_arg"
        ) as mock_serialize:
            mock_serialize.side_effect = SerializationError("Known error")
            with pytest.raises(SerializationError, match="Known error"):
                serialize_args((1, 2))

    def test_serialize_args_unexpected_error(self):
        """Test serialize_args handles unexpected exceptions."""
        with patch(
            "runpod_flash.runtime.serialization.serialize_arg"
        ) as mock_serialize:
            mock_serialize.side_effect = RuntimeError("Unexpected error")
            with pytest.raises(SerializationError, match="Failed to serialize args"):
                serialize_args((1, 2))


class TestSerializeKwargs:
    """Test serialize_kwargs function."""

    def test_serialize_kwargs(self):
        """Test serializing keyword arguments."""
        result = serialize_kwargs({"key1": 42, "key2": "test"})
        assert len(result) == 2
        assert "key1" in result
        assert "key2" in result
        assert all(isinstance(v, str) for v in result.values())

    def test_serialize_empty_kwargs(self):
        """Test serializing empty kwargs dict."""
        result = serialize_kwargs({})
        assert result == {}

    def test_serialize_kwargs_propagates_serialization_error(self):
        """Test serialize_kwargs propagates SerializationError."""
        with patch(
            "runpod_flash.runtime.serialization.serialize_arg"
        ) as mock_serialize:
            mock_serialize.side_effect = SerializationError("Known error")
            with pytest.raises(SerializationError, match="Known error"):
                serialize_kwargs({"key": 42})

    def test_serialize_kwargs_unexpected_error(self):
        """Test serialize_kwargs handles unexpected exceptions."""
        with patch(
            "runpod_flash.runtime.serialization.serialize_arg"
        ) as mock_serialize:
            mock_serialize.side_effect = RuntimeError("Unexpected error")
            with pytest.raises(SerializationError, match="Failed to serialize kwargs"):
                serialize_kwargs({"key": 42})


class TestDeserializeArg:
    """Test deserialize_arg function."""

    def test_deserialize_simple_arg(self):
        """Test deserializing a simple argument."""
        # First serialize something
        serialized = serialize_arg(42)
        # Then deserialize it
        result = deserialize_arg(serialized)
        assert result == 42

    def test_deserialize_raises_on_invalid_base64(self):
        """Test deserialize_arg raises on invalid base64."""
        with pytest.raises(SerializationError, match="Failed to deserialize argument"):
            deserialize_arg("not-valid-base64!!!")


class TestDeserializeArgs:
    """Test deserialize_args function."""

    def test_deserialize_multiple_args(self):
        """Test deserializing multiple arguments."""
        serialized = serialize_args((1, "test", [1, 2, 3]))
        result = deserialize_args(serialized)
        assert result == [1, "test", [1, 2, 3]]

    def test_deserialize_empty_args(self):
        """Test deserializing empty args list."""
        result = deserialize_args([])
        assert result == []

    def test_deserialize_args_propagates_serialization_error(self):
        """Test deserialize_args propagates SerializationError."""
        with patch(
            "runpod_flash.runtime.serialization.deserialize_arg"
        ) as mock_deserialize:
            mock_deserialize.side_effect = SerializationError("Known error")
            with pytest.raises(SerializationError, match="Known error"):
                deserialize_args(["arg1", "arg2"])

    def test_deserialize_args_unexpected_error(self):
        """Test deserialize_args handles unexpected exceptions."""
        with patch(
            "runpod_flash.runtime.serialization.deserialize_arg"
        ) as mock_deserialize:
            mock_deserialize.side_effect = RuntimeError("Unexpected error")
            with pytest.raises(SerializationError, match="Failed to deserialize args"):
                deserialize_args(["arg1", "arg2"])


class TestDeserializeKwargs:
    """Test deserialize_kwargs function."""

    def test_deserialize_kwargs(self):
        """Test deserializing keyword arguments."""
        serialized = serialize_kwargs({"key1": 42, "key2": "test"})
        result = deserialize_kwargs(serialized)
        assert result == {"key1": 42, "key2": "test"}

    def test_deserialize_empty_kwargs(self):
        """Test deserializing empty kwargs dict."""
        result = deserialize_kwargs({})
        assert result == {}

    def test_deserialize_kwargs_propagates_serialization_error(self):
        """Test deserialize_kwargs propagates SerializationError."""
        with patch(
            "runpod_flash.runtime.serialization.deserialize_arg"
        ) as mock_deserialize:
            mock_deserialize.side_effect = SerializationError("Known error")
            with pytest.raises(SerializationError, match="Known error"):
                deserialize_kwargs({"key": "value"})

    def test_deserialize_kwargs_unexpected_error(self):
        """Test deserialize_kwargs handles unexpected exceptions."""
        with patch(
            "runpod_flash.runtime.serialization.deserialize_arg"
        ) as mock_deserialize:
            mock_deserialize.side_effect = RuntimeError("Unexpected error")
            with pytest.raises(
                SerializationError, match="Failed to deserialize kwargs"
            ):
                deserialize_kwargs({"key": "value"})
