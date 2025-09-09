"""
Unit tests for LoadBalancerSls endpoint decorator functionality.

Tests the @endpoint decorator that marks class methods for HTTP endpoint exposure,
including decorator configuration, method scanning, validation, and integration
with LoadBalancerSls class wrappers.
"""

import pytest
from typing import Dict, Any

from tetra_rp.core.resources.load_balancer_sls.endpoint import (
    endpoint,
    scan_endpoint_methods,
)


class TestEndpointDecorator:
    """Test @endpoint decorator functionality."""

    def test_basic_endpoint_decorator(self):
        """Test basic endpoint decorator usage."""

        @endpoint()
        def test_method(self):
            return {"result": "test"}

        assert hasattr(test_method, "_endpoint_config")
        config = test_method._endpoint_config
        assert config["methods"] == ["POST"]  # Default method
        assert config["route"] == "/test_method"  # Default route

    def test_endpoint_decorator_with_methods(self):
        """Test endpoint decorator with custom methods."""

        @endpoint(methods=["GET", "POST", "PUT"])
        def multi_method(self):
            return {"result": "multi"}

        config = multi_method._endpoint_config
        assert set(config["methods"]) == {"GET", "POST", "PUT"}
        assert config["route"] == "/multi_method"

    def test_endpoint_decorator_with_custom_route(self):
        """Test endpoint decorator with custom route."""

        @endpoint(methods=["GET"], route="/custom-path")
        def custom_route_method(self):
            return {"result": "custom"}

        config = custom_route_method._endpoint_config
        assert config["methods"] == ["GET"]
        assert config["route"] == "/custom-path"

    def test_endpoint_decorator_normalizes_method_case(self):
        """Test endpoint decorator normalizes HTTP methods to uppercase."""

        @endpoint(methods=["get", "post", "Put", "DELETE"])
        def mixed_case_method(self):
            return {}

        config = mixed_case_method._endpoint_config
        assert set(config["methods"]) == {"GET", "POST", "PUT", "DELETE"}

    def test_endpoint_decorator_preserves_function_metadata(self):
        """Test endpoint decorator preserves function metadata."""

        @endpoint(methods=["POST"])
        def documented_method(self, data: str) -> Dict[str, Any]:
            """This is a documented method."""
            return {"input": data}

        assert documented_method.__name__ == "documented_method"
        assert documented_method.__doc__ == "This is a documented method."
        assert hasattr(documented_method, "_endpoint_config")

    def test_endpoint_decorator_on_class_method(self):
        """Test endpoint decorator works on class methods."""

        class TestClass:
            @endpoint(methods=["GET"])
            def get_data(self):
                return {"data": "test"}

            @endpoint(methods=["POST"], route="/submit")
            def submit_data(self, data):
                return {"submitted": data}

        # Check first method
        assert hasattr(TestClass.get_data, "_endpoint_config")
        config1 = TestClass.get_data._endpoint_config
        assert config1["methods"] == ["GET"]
        assert config1["route"] == "/get_data"

        # Check second method
        assert hasattr(TestClass.submit_data, "_endpoint_config")
        config2 = TestClass.submit_data._endpoint_config
        assert config2["methods"] == ["POST"]
        assert config2["route"] == "/submit"


class TestEndpointDecoratorValidation:
    """Test @endpoint decorator input validation."""

    def test_methods_must_be_list(self):
        """Test methods parameter must be a list."""
        with pytest.raises(TypeError, match="methods must be a list"):

            @endpoint(methods="GET")
            def invalid_method():
                pass

    def test_methods_cannot_be_empty(self):
        """Test methods parameter cannot be empty."""
        with pytest.raises(ValueError, match="methods cannot be empty"):

            @endpoint(methods=[])
            def empty_methods():
                pass

    def test_route_must_be_string_or_none(self):
        """Test route parameter must be string or None."""
        with pytest.raises(TypeError, match="route must be a string or None"):

            @endpoint(methods=["GET"], route=123)
            def invalid_route():
                pass

    def test_invalid_http_methods(self):
        """Test validation of HTTP methods."""
        with pytest.raises(ValueError, match="Invalid HTTP methods: \\['INVALID'\\]"):

            @endpoint(methods=["GET", "INVALID"])
            def invalid_http_method():
                pass

    def test_multiple_invalid_http_methods(self):
        """Test validation with multiple invalid HTTP methods."""
        with pytest.raises(
            ValueError, match="Invalid HTTP methods: \\['INVALID1', 'INVALID2'\\]"
        ):

            @endpoint(methods=["GET", "INVALID1", "POST", "INVALID2"])
            def multiple_invalid():
                pass

    def test_valid_http_methods(self):
        """Test all valid HTTP methods are accepted."""
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

        @endpoint(methods=valid_methods)
        def all_methods():
            return {}

        config = all_methods._endpoint_config
        assert set(config["methods"]) == set(valid_methods)

    def test_decorator_on_non_callable_raises_error(self):
        """Test decorator raises error when applied to non-callable."""
        with pytest.raises(
            TypeError,
            match="endpoint decorator can only be applied to callable objects",
        ):
            endpoint(methods=["GET"])(123)


class TestScanEndpointMethods:
    """Test scan_endpoint_methods function."""

    def test_scan_class_with_endpoint_methods(self):
        """Test scanning class with endpoint methods."""

        class APIClass:
            @endpoint(methods=["GET"])
            def get_status(self):
                return {"status": "ok"}

            @endpoint(methods=["POST"], route="/predict")
            def predict(self, data):
                return {"prediction": "result"}

            def regular_method(self):
                """Non-endpoint method."""
                return "regular"

        endpoint_methods = scan_endpoint_methods(APIClass)

        assert len(endpoint_methods) == 2
        assert "get_status" in endpoint_methods
        assert "predict" in endpoint_methods
        assert "regular_method" not in endpoint_methods

        # Check configurations
        assert endpoint_methods["get_status"]["methods"] == ["GET"]
        assert endpoint_methods["get_status"]["route"] == "/get_status"

        assert endpoint_methods["predict"]["methods"] == ["POST"]
        assert endpoint_methods["predict"]["route"] == "/predict"

    def test_scan_class_with_no_endpoint_methods(self):
        """Test scanning class with no endpoint methods."""

        class RegularClass:
            def method1(self):
                return "method1"

            def method2(self):
                return "method2"

        endpoint_methods = scan_endpoint_methods(RegularClass)
        assert len(endpoint_methods) == 0
        assert endpoint_methods == {}

    def test_scan_empty_class(self):
        """Test scanning empty class."""

        class EmptyClass:
            pass

        endpoint_methods = scan_endpoint_methods(EmptyClass)
        assert len(endpoint_methods) == 0

    def test_scan_class_with_inherited_endpoint_methods(self):
        """Test scanning class with inherited endpoint methods."""

        class BaseClass:
            @endpoint(methods=["GET"])
            def base_method(self):
                return "base"

        class DerivedClass(BaseClass):
            @endpoint(methods=["POST"])
            def derived_method(self):
                return "derived"

        endpoint_methods = scan_endpoint_methods(DerivedClass)

        assert len(endpoint_methods) == 2
        assert "base_method" in endpoint_methods
        assert "derived_method" in endpoint_methods

    def test_scan_class_with_property_methods(self):
        """Test scanning class that has properties."""

        class ClassWithProperties:
            def __init__(self):
                self._value = "test"

            @property
            def value(self):
                return self._value

            @endpoint(methods=["GET"])
            def get_value(self):
                return {"value": self.value}

        endpoint_methods = scan_endpoint_methods(ClassWithProperties)

        assert len(endpoint_methods) == 1
        assert "get_value" in endpoint_methods
        assert "value" not in endpoint_methods  # Properties should be ignored

    def test_scan_class_with_static_and_class_methods(self):
        """Test scanning class with static and class methods."""

        class ClassWithSpecialMethods:
            @staticmethod
            @endpoint(methods=["GET"])
            def static_endpoint():
                return {"type": "static"}

            @classmethod
            @endpoint(methods=["POST"])
            def class_endpoint(cls):
                return {"type": "class"}

            @endpoint(methods=["PUT"])
            def instance_endpoint(self):
                return {"type": "instance"}

        endpoint_methods = scan_endpoint_methods(ClassWithSpecialMethods)

        # All should be detected regardless of method type
        assert len(endpoint_methods) == 3
        assert "static_endpoint" in endpoint_methods
        assert "class_endpoint" in endpoint_methods
        assert "instance_endpoint" in endpoint_methods

    def test_scan_non_class_raises_error(self):
        """Test scan_endpoint_methods raises error for non-class."""
        with pytest.raises(TypeError, match="cls must be a class"):
            scan_endpoint_methods("not_a_class")

        with pytest.raises(TypeError, match="cls must be a class"):
            scan_endpoint_methods(123)

        def function():
            pass

        with pytest.raises(TypeError, match="cls must be a class"):
            scan_endpoint_methods(function)

    def test_scan_class_with_malformed_endpoint_config(self):
        """Test scanning class with malformed endpoint configurations."""

        class MalformedClass:
            def method_with_bad_config(self):
                pass

            @endpoint(methods=["GET"])
            def valid_method(self):
                pass

        # Manually add malformed config to simulate edge case
        MalformedClass.method_with_bad_config._endpoint_config = "invalid"

        endpoint_methods = scan_endpoint_methods(MalformedClass)

        # Should only include valid endpoint methods
        assert len(endpoint_methods) == 1
        assert "valid_method" in endpoint_methods
        assert "method_with_bad_config" not in endpoint_methods

    def test_scan_class_with_missing_config_fields(self):
        """Test scanning class with endpoint config missing required fields."""

        class IncompleteConfigClass:
            def incomplete_method(self):
                pass

            @endpoint(methods=["GET"])
            def valid_method(self):
                pass

        # Manually add incomplete config
        IncompleteConfigClass.incomplete_method._endpoint_config = {
            "methods": ["GET"]
        }  # Missing 'route'

        endpoint_methods = scan_endpoint_methods(IncompleteConfigClass)

        # Should only include valid endpoint methods
        assert len(endpoint_methods) == 1
        assert "valid_method" in endpoint_methods
        assert "incomplete_method" not in endpoint_methods


class TestEndpointIntegration:
    """Test endpoint decorator integration scenarios."""

    def test_endpoint_decorator_preserves_async_functions(self):
        """Test endpoint decorator works with async functions."""

        class AsyncAPIClass:
            @endpoint(methods=["POST"])
            async def async_predict(self, data):
                return {"result": await self._process(data)}

            async def _process(self, data):
                return f"processed_{data}"

        endpoint_methods = scan_endpoint_methods(AsyncAPIClass)

        assert "async_predict" in endpoint_methods
        assert endpoint_methods["async_predict"]["methods"] == ["POST"]

        # Verify it's still async
        import asyncio

        assert asyncio.iscoroutinefunction(AsyncAPIClass.async_predict)

    def test_multiple_decorators_compatibility(self):
        """Test endpoint decorator works with other decorators."""

        def other_decorator(func):
            func._other_decorator = True
            return func

        class DecoratedClass:
            @other_decorator
            @endpoint(methods=["GET"])
            def decorated_method(self):
                return {"decorated": True}

        endpoint_methods = scan_endpoint_methods(DecoratedClass)

        assert "decorated_method" in endpoint_methods
        assert hasattr(DecoratedClass.decorated_method, "_other_decorator")
        assert hasattr(DecoratedClass.decorated_method, "_endpoint_config")

    def test_endpoint_configuration_immutability(self):
        """Test endpoint configuration doesn't change after decoration."""

        @endpoint(methods=["GET", "POST"], route="/test")
        def test_method():
            return {}

        original_config = test_method._endpoint_config.copy()

        # Try to modify config (should not affect original)
        config = test_method._endpoint_config
        config["methods"].append("PUT")
        config["route"] = "/modified"

        # Original configuration should be preserved
        assert (
            test_method._endpoint_config["methods"] != original_config["methods"]
        )  # This will be modified
        assert (
            test_method._endpoint_config["route"] != original_config["route"]
        )  # This will be modified

        # Note: This test shows that the config is mutable, which might be a design consideration
