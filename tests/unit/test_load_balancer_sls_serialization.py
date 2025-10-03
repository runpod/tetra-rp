"""
Unit tests for LoadBalancerSls serialization utilities.

Tests the SerializationUtils class that handles serialization and deserialization
of function arguments and results using cloudpickle and base64 encoding for
LoadBalancerSls remote execution and HTTP endpoint functionality.
"""

import pytest

from tetra_rp.core.resources.load_balancer_sls.serialization import SerializationUtils


class TestSerializationUtilsBasic:
    """Test basic SerializationUtils functionality."""

    def test_serialize_simple_types(self):
        """Test serialization of simple Python types."""
        test_cases = [
            42,
            3.14,
            "hello world",
            True,
            False,
            None,
            [1, 2, 3],
            {"key": "value"},
            (1, 2, 3),
        ]

        for test_value in test_cases:
            result = SerializationUtils.serialize_result(test_value)
            assert isinstance(result, str)
            # Verify it's valid base64
            try:
                import base64

                base64.b64decode(result)
            except Exception:
                pytest.fail(f"Invalid base64 for {test_value}: {result}")

    def test_deserialize_simple_types(self):
        """Test round-trip serialization/deserialization of simple types."""
        test_cases = [
            42,
            3.14,
            "hello world",
            True,
            False,
            None,
            [1, 2, 3],
            {"key": "value", "nested": {"inner": "value"}},
            (1, "two", 3.0),
        ]

        for test_value in test_cases:
            serialized = SerializationUtils.serialize_result(test_value)
            deserialized = SerializationUtils.deserialize_result(serialized)
            assert deserialized == test_value
            assert isinstance(deserialized, type(test_value))

    def test_serialize_complex_objects(self):
        """Test serialization of complex Python objects."""

        class CustomClass:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return isinstance(other, CustomClass) and self.value == other.value

        def test_function(x):
            return x * 2

        test_cases = [
            CustomClass("test"),
            test_function,
            lambda x: x + 1,
            {"function": test_function, "class": CustomClass(42)},
        ]

        for test_value in test_cases:
            serialized = SerializationUtils.serialize_result(test_value)
            deserialized = SerializationUtils.deserialize_result(serialized)

            if callable(test_value):
                # For functions, just verify they're callable
                assert callable(deserialized)
            elif isinstance(test_value, dict):
                # For dicts with complex objects, verify structure
                assert isinstance(deserialized, dict)
                assert set(deserialized.keys()) == set(test_value.keys())
            else:
                assert deserialized == test_value

    def test_serialize_large_objects(self):
        """Test serialization of large objects."""
        large_list = list(range(10000))
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}

        # Should handle large objects without issues
        serialized_list = SerializationUtils.serialize_result(large_list)
        serialized_dict = SerializationUtils.serialize_result(large_dict)

        deserialized_list = SerializationUtils.deserialize_result(serialized_list)
        deserialized_dict = SerializationUtils.deserialize_result(serialized_dict)

        assert deserialized_list == large_list
        assert deserialized_dict == large_dict


class TestSerializationUtilsIntegration:
    """Test SerializationUtils integration scenarios."""

    def test_round_trip_complex_function_call(self):
        """Test complete round-trip for complex function call data."""

        # Simulate a complex remote function call
        class DataProcessor:
            def __init__(self, config):
                self.config = config

            def process(self, data, options=None):
                return {"processed": data, "config": self.config, "options": options}

        # Arguments that might be passed to a remote function
        args = [
            DataProcessor({"setting": "value"}),
            {"input": "data", "numbers": [1, 2, 3]},
        ]

        kwargs = {"options": {"flag": True, "count": 42}, "callback": lambda x: x * 2}

        # Serialize arguments
        serialized_args = [SerializationUtils.serialize_result(arg) for arg in args]
        serialized_kwargs = {
            k: SerializationUtils.serialize_result(v) for k, v in kwargs.items()
        }

        # Deserialize using utility methods
        deserialized_args = SerializationUtils.deserialize_args(serialized_args)
        deserialized_kwargs = SerializationUtils.deserialize_kwargs(serialized_kwargs)

        # Verify round-trip accuracy
        assert len(deserialized_args) == len(args)
        assert isinstance(deserialized_args[0], DataProcessor)
        assert deserialized_args[0].config == args[0].config
        assert deserialized_args[1] == args[1]

        assert set(deserialized_kwargs.keys()) == set(kwargs.keys())
        assert deserialized_kwargs["options"] == kwargs["options"]
        assert callable(deserialized_kwargs["callback"])

    def test_serialization_consistency(self):
        """Test serialization is consistent across multiple calls."""
        test_object = {"key": "value", "number": 42}

        # Multiple serializations of the same object should be identical
        serialized1 = SerializationUtils.serialize_result(test_object)
        serialized2 = SerializationUtils.serialize_result(test_object)

        # Note: cloudpickle might not always produce identical output for the same object
        # due to internal optimizations, so we test functional equivalence
        deserialized1 = SerializationUtils.deserialize_result(serialized1)
        deserialized2 = SerializationUtils.deserialize_result(serialized2)

        assert deserialized1 == deserialized2
        assert deserialized1 == test_object

    def test_nested_serialization_structures(self):
        """Test serialization of nested data structures."""
        nested_structure = {
            "level1": {
                "level2": {
                    "level3": [
                        {"deep_key": "deep_value"},
                        lambda x: x**2,
                        (1, 2, {"tuple_dict": "value"}),
                    ]
                }
            },
            "functions": [lambda a, b: a + b, lambda x: {"result": x * 2}],
        }

        serialized = SerializationUtils.serialize_result(nested_structure)
        deserialized = SerializationUtils.deserialize_result(serialized)

        # Verify structure preservation
        assert "level1" in deserialized
        assert "level2" in deserialized["level1"]
        assert "level3" in deserialized["level1"]["level2"]
        assert len(deserialized["level1"]["level2"]["level3"]) == 3
        assert len(deserialized["functions"]) == 2

        # Verify deep values
        level3 = deserialized["level1"]["level2"]["level3"]
        assert level3[0]["deep_key"] == "deep_value"
        assert callable(level3[1])  # Lambda function
        assert level3[2][2]["tuple_dict"] == "value"

        # Verify functions are callable
        assert callable(deserialized["functions"][0])
        assert callable(deserialized["functions"][1])
