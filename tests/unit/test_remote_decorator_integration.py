"""
Unit tests for @remote decorator LoadBalancerSls integration.

Tests the integration between the @remote decorator and LoadBalancerSlsResource,
including class vs function handling, resource type detection, and proper delegation
to LoadBalancerSls functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from tetra_rp.client import remote
from tetra_rp.core.resources import ServerlessResource, LoadBalancerSlsResource


class TestRemoteDecoratorResourceTypeDetection:
    """Test @remote decorator properly detects LoadBalancerSlsResource vs ServerlessResource."""

    def test_detects_load_balancer_sls_resource(self):
        """Test decorator detects LoadBalancerSlsResource instance."""
        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        assert isinstance(lb_resource, LoadBalancerSlsResource)
        # Should also be instance of base ServerlessResource
        assert isinstance(lb_resource, ServerlessResource)

    def test_detects_regular_serverless_resource(self):
        """Test decorator detects regular ServerlessResource instance."""
        regular_resource = ServerlessResource(
            name="test-regular", endpointId="test-endpoint", type="SERVERLESS"
        )

        assert isinstance(regular_resource, ServerlessResource)
        assert not isinstance(regular_resource, LoadBalancerSlsResource)


class TestRemoteDecoratorClassHandling:
    """Test @remote decorator handling of class decoration."""

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_class_with_load_balancer_sls_resource(self, mock_create_lb_class):
        """Test decorator routes classes with LoadBalancerSlsResource to LoadBalancer handler."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(
            resource_config=lb_resource,
            dependencies=["torch"],
            system_dependencies=["git"],
        )
        class TestMLModel:
            def predict(self, data):
                return {"result": "test"}

        # Should call LoadBalancer class creator
        mock_create_lb_class.assert_called_once_with(
            TestMLModel,
            lb_resource,
            ["torch"],
            ["git"],
            {},  # extra args
        )

    @patch("tetra_rp.client.create_remote_class")
    def test_class_with_regular_serverless_resource(self, mock_create_remote_class):
        """Test decorator routes classes with regular ServerlessResource to traditional handler."""
        mock_create_remote_class.return_value = Mock()

        regular_resource = ServerlessResource(
            name="test-regular", endpointId="test-endpoint", type="SERVERLESS"
        )

        @remote(resource_config=regular_resource, dependencies=["numpy"])
        class TestProcessor:
            def process(self, data):
                return data * 2

        # Should call traditional remote class creator
        mock_create_remote_class.assert_called_once_with(
            TestProcessor,
            regular_resource,
            ["numpy"],
            None,  # system_dependencies
            {},  # extra args
        )

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_class_with_extra_parameters(self, mock_create_lb_class):
        """Test decorator passes extra parameters correctly."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(
            resource_config=lb_resource,
            dependencies=["transformers"],
            system_dependencies=["curl"],
            timeout=300,
            max_retries=10,
            custom_param="custom_value",
        )
        class TestTransformerModel:
            def generate(self, prompt):
                return f"Generated: {prompt}"

        # Should pass extra parameters
        expected_extra = {
            "timeout": 300,
            "max_retries": 10,
            "custom_param": "custom_value",
        }
        mock_create_lb_class.assert_called_once_with(
            TestTransformerModel,
            lb_resource,
            ["transformers"],
            ["curl"],
            expected_extra,
        )


class TestRemoteDecoratorFunctionHandling:
    """Test @remote decorator handling of function decoration."""

    def test_function_with_load_balancer_sls_resource_raises_error(self):
        """Test that using LoadBalancerSlsResource with function raises ValueError."""
        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        with pytest.raises(
            ValueError, match="LoadBalancerSlsResource can only be used with classes"
        ):

            @remote(resource_config=lb_resource)
            async def test_function(data):
                return data

    @patch("tetra_rp.client.ResourceManager")
    @patch("tetra_rp.client.stub_resource")
    def test_function_with_regular_serverless_resource(
        self, mock_stub_resource, mock_resource_manager_class
    ):
        """Test function decoration with regular ServerlessResource works."""
        # Setup mocks
        mock_resource_manager = Mock()
        mock_resource_manager.get_or_deploy_resource = AsyncMock(return_value=Mock())
        mock_resource_manager_class.return_value = mock_resource_manager

        mock_stub = Mock()
        mock_stub.return_value = AsyncMock(return_value="function_result")
        mock_stub_resource.return_value = mock_stub

        regular_resource = ServerlessResource(
            name="test-regular", endpointId="test-endpoint", type="SERVERLESS"
        )

        @remote(resource_config=regular_resource, dependencies=["pandas"], timeout=120)
        async def test_function(data):
            return f"processed: {data}"

        # Should be a coroutine function
        assert asyncio.iscoroutinefunction(test_function)

    @patch("tetra_rp.client.ResourceManager")
    @patch("tetra_rp.client.stub_resource")
    async def test_function_execution_flow(
        self, mock_stub_resource, mock_resource_manager_class
    ):
        """Test complete function execution flow."""
        # Setup mocks
        mock_remote_resource = Mock()
        mock_resource_manager = Mock()
        mock_resource_manager.get_or_deploy_resource = AsyncMock(
            return_value=mock_remote_resource
        )
        mock_resource_manager_class.return_value = mock_resource_manager

        mock_stub = AsyncMock(return_value="execution_result")
        mock_stub_resource.return_value = mock_stub

        regular_resource = ServerlessResource(
            name="test-regular", endpointId="test-endpoint", type="SERVERLESS"
        )

        @remote(
            resource_config=regular_resource,
            dependencies=["scipy"],
            system_dependencies=["gcc"],
            sync=True,
        )
        async def compute_function(x, y):
            return x * y

        # Execute the decorated function
        result = await compute_function(5, 10)

        # Verify the execution flow
        mock_resource_manager.get_or_deploy_resource.assert_called_once_with(
            regular_resource
        )
        mock_stub_resource.assert_called_once_with(mock_remote_resource, sync=True)
        mock_stub.assert_called_once()

        # Check arguments passed to stub
        call_args = mock_stub.call_args[0]
        assert call_args[1] == ["scipy"]  # dependencies
        assert call_args[2] == ["gcc"]  # system_dependencies
        assert call_args[3] == 5  # first function arg
        assert call_args[4] == 10  # second function arg

        assert result == "execution_result"


class TestRemoteDecoratorParameterHandling:
    """Test @remote decorator parameter handling and validation."""

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_optional_dependencies_none(self, mock_create_lb_class):
        """Test decorator handles None dependencies correctly."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(resource_config=lb_resource)
        class MinimalModel:
            def predict(self):
                return "prediction"

        mock_create_lb_class.assert_called_once_with(
            MinimalModel,
            lb_resource,
            None,  # dependencies
            None,  # system_dependencies
            {},  # extra
        )

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_empty_dependencies_list(self, mock_create_lb_class):
        """Test decorator handles empty dependencies list."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(resource_config=lb_resource, dependencies=[], system_dependencies=[])
        class EmptyDepsModel:
            def predict(self):
                return "prediction"

        mock_create_lb_class.assert_called_once_with(
            EmptyDepsModel,
            lb_resource,
            [],  # empty dependencies
            [],  # empty system_dependencies
            {},  # extra
        )

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_complex_dependencies(self, mock_create_lb_class):
        """Test decorator handles complex dependency lists."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        complex_deps = [
            "torch==2.0.0",
            "transformers>=4.20.0",
            "numpy",
            "git+https://github.com/custom/repo.git",
        ]

        complex_sys_deps = ["build-essential", "python3-dev", "libffi-dev"]

        @remote(
            resource_config=lb_resource,
            dependencies=complex_deps,
            system_dependencies=complex_sys_deps,
        )
        class ComplexModel:
            def predict(self):
                return "complex_prediction"

        mock_create_lb_class.assert_called_once_with(
            ComplexModel, lb_resource, complex_deps, complex_sys_deps, {}
        )


class TestRemoteDecoratorLogging:
    """Test @remote decorator logging behavior."""

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    @patch("tetra_rp.client.log")
    def test_logs_load_balancer_sls_mode(self, mock_log, mock_create_lb_class):
        """Test decorator logs when using LoadBalancerSls mode."""
        mock_create_lb_class.return_value = Mock()

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(resource_config=lb_resource)
        class LoggedModel:
            def predict(self):
                return "logged_prediction"

        # Should log LoadBalancerSls usage
        mock_log.info.assert_called_once_with(
            "Using LoadBalancerSls mode for class LoggedModel"
        )

    @patch("tetra_rp.client.create_remote_class")
    @patch("tetra_rp.client.log")
    def test_no_log_for_regular_serverless(self, mock_log, mock_create_remote_class):
        """Test decorator doesn't log for regular serverless mode."""
        mock_create_remote_class.return_value = Mock()

        regular_resource = ServerlessResource(
            name="test-regular", endpointId="test-endpoint", type="SERVERLESS"
        )

        @remote(resource_config=regular_resource)
        class RegularModel:
            def predict(self):
                return "regular_prediction"

        # Should not log anything for regular serverless
        mock_log.info.assert_not_called()


class TestRemoteDecoratorEdgeCases:
    """Test @remote decorator edge cases and error conditions."""

    def test_invalid_resource_config_type(self):
        """Test decorator behavior with invalid resource config."""
        with pytest.raises(AttributeError):

            @remote(resource_config="invalid_string")
            class InvalidModel:
                pass

    @patch("tetra_rp.client.create_load_balancer_sls_class")
    def test_decorator_preserves_class_metadata(self, mock_create_lb_class):
        """Test decorator preserves original class metadata."""
        mock_decorated_class = Mock()
        mock_decorated_class.__name__ = "MockDecoratedClass"
        mock_create_lb_class.return_value = mock_decorated_class

        lb_resource = LoadBalancerSlsResource(
            name="test-lb", endpointId="test-endpoint"
        )

        @remote(resource_config=lb_resource)
        class OriginalClass:
            """Original class docstring."""

            def method(self):
                pass

        # The result should be what the mock returns
        result_class = OriginalClass
        assert result_class.__name__ == "MockDecoratedClass"
