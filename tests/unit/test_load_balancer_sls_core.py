"""
Unit tests for LoadBalancerSls core functionality.

Tests the core LoadBalancerSls client functionality including:
- Initialization and configuration
- Remote class decoration
"""

import pytest
from unittest.mock import patch

from tetra_rp.core.resources.load_balancer_sls.client import (
    LoadBalancerSls,
    DeploymentClassWrapper,
    DeploymentInstanceWrapper,
)
from tetra_rp.core.resources.load_balancer_sls.exceptions import (
    LoadBalancerSlsConfigurationError,
)


class TestLoadBalancerSlsInitialization:
    """Test LoadBalancerSls client initialization."""

    def test_loadbalancersls_init_with_endpoint_url(self):
        """Test LoadBalancerSls initialization with endpoint URL."""
        endpoint_url = "https://test-endpoint.api.runpod.ai"
        api_key = "test-api-key"

        client = LoadBalancerSls(
            endpoint_url=endpoint_url,
            api_key=api_key,
            timeout=120.0,
            max_retries=5,
            retry_delay=2.0,
        )

        assert client.endpoint_url == endpoint_url
        assert client.api_key == api_key
        assert client.timeout == 120.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        assert client._session is None
        assert not client._health_checked

    def test_loadbalancersls_init_with_env_api_key(self):
        """Test LoadBalancerSls initialization with environment API key."""
        endpoint_url = "https://test-endpoint.api.runpod.ai"

        with patch.dict("os.environ", {"RUNPOD_API_KEY": "env-api-key"}):
            client = LoadBalancerSls(endpoint_url=endpoint_url)
            assert client.api_key == "env-api-key"

    def test_loadbalancersls_init_no_endpoint_url_raises_error(self):
        """Test LoadBalancerSls initialization without endpoint URL raises error."""
        with pytest.raises(
            LoadBalancerSlsConfigurationError, match="endpoint_url is required"
        ):
            LoadBalancerSls()

    def test_loadbalancersls_init_strips_trailing_slash(self):
        """Test LoadBalancerSls initialization strips trailing slash from endpoint URL."""
        client = LoadBalancerSls(endpoint_url="https://test-endpoint.api.runpod.ai/")
        assert client.endpoint_url == "https://test-endpoint.api.runpod.ai"

    def test_loadbalancersls_init_defaults(self):
        """Test LoadBalancerSls initialization with default values."""
        client = LoadBalancerSls(endpoint_url="https://test.api.runpod.ai")

        assert client.timeout == 300.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client._health_check_retries == 3


class TestLoadBalancerSlsRemoteClassDecorator:
    """Test LoadBalancerSls remote_class decorator functionality."""

    @pytest.fixture
    def client(self):
        return LoadBalancerSls(
            endpoint_url="https://test-endpoint.api.runpod.ai", api_key="test-api-key"
        )

    def test_remote_class_decorator_returns_wrapper(self, client):
        """Test remote_class decorator returns DeploymentClassWrapper."""
        dependencies = ["numpy"]
        system_dependencies = ["apt-package"]

        @client.remote_class(
            dependencies=dependencies, system_dependencies=system_dependencies
        )
        class TestClass:
            def test_method(self):
                return "test"

        assert isinstance(TestClass, DeploymentClassWrapper)
        assert TestClass._dependencies == dependencies
        assert TestClass._system_dependencies == system_dependencies

    def test_remote_class_decorator_defaults(self, client):
        """Test remote_class decorator with default parameters."""

        @client.remote_class()
        class TestClass:
            def test_method(self):
                return "test"

        assert isinstance(TestClass, DeploymentClassWrapper)
        assert TestClass._dependencies == []
        assert TestClass._system_dependencies == []

    def test_remote_class_instantiation(self, client):
        """Test instantiating a remote class creates instance wrapper."""

        @client.remote_class()
        class TestClass:
            def __init__(self, value):
                self.value = value

            def get_value(self):
                return self.value

        instance = TestClass(42)
        assert isinstance(instance, DeploymentInstanceWrapper)
        assert instance._constructor_args == (42,)


if __name__ == "__main__":
    pytest.main([__file__])
