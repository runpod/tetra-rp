"""Unit tests for LoadBalancerSlsStub functionality."""

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import cloudpickle

from tetra_rp import remote, LoadBalancerSlsResource
from tetra_rp.stubs.load_balancer_sls import LoadBalancerSlsStub


# Create test resources
test_lb_resource = LoadBalancerSlsResource(
    name="test-lb",
    imageName="test:latest",
)


class TestLoadBalancerSlsStubPrepareRequest:
    """Test suite for _prepare_request method."""

    def test_prepare_request_with_no_args(self):
        """Test request preparation with no arguments."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        def test_func():
            return "result"

        request = stub._prepare_request(test_func, None, None, True)

        assert request["function_name"] == "test_func"
        assert "def test_func" in request["function_code"]
        assert request["dependencies"] == []
        assert request["system_dependencies"] == []
        assert request["accelerate_downloads"] is True
        assert "args" not in request or request["args"] == []
        assert "kwargs" not in request or request["kwargs"] == {}

    def test_prepare_request_with_args(self):
        """Test request preparation with positional arguments."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        def add(x, y):
            return x + y

        arg1 = 5
        arg2 = 3
        request = stub._prepare_request(add, None, None, True, arg1, arg2)

        assert request["function_name"] == "add"
        assert len(request["args"]) == 2

        # Verify args are properly serialized
        decoded_arg1 = cloudpickle.loads(base64.b64decode(request["args"][0]))
        decoded_arg2 = cloudpickle.loads(base64.b64decode(request["args"][1]))
        assert decoded_arg1 == 5
        assert decoded_arg2 == 3

    def test_prepare_request_with_kwargs(self):
        """Test request preparation with keyword arguments."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        request = stub._prepare_request(greet, None, None, True, name="Alice", greeting="Hi")

        assert "kwargs" in request
        assert len(request["kwargs"]) == 2

        # Verify kwargs are properly serialized
        decoded_name = cloudpickle.loads(base64.b64decode(request["kwargs"]["name"]))
        decoded_greeting = cloudpickle.loads(
            base64.b64decode(request["kwargs"]["greeting"])
        )
        assert decoded_name == "Alice"
        assert decoded_greeting == "Hi"

    def test_prepare_request_with_dependencies(self):
        """Test request preparation includes dependencies."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        def test_func():
            return "result"

        dependencies = ["requests", "numpy"]
        system_deps = ["git"]

        request = stub._prepare_request(
            test_func, dependencies, system_deps, True
        )

        assert request["dependencies"] == dependencies
        assert request["system_dependencies"] == system_deps


class TestLoadBalancerSlsStubHandleResponse:
    """Test suite for _handle_response method."""

    def test_handle_response_success(self):
        """Test successful response handling."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        result_value = {"status": "ok", "value": 42}
        result_b64 = base64.b64encode(cloudpickle.dumps(result_value)).decode("utf-8")

        response = {"success": True, "result": result_b64}

        result = stub._handle_response(response)

        assert result == result_value

    def test_handle_response_error(self):
        """Test error response handling."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        response = {"success": False, "error": "Function execution failed"}

        with pytest.raises(Exception, match="Remote execution failed"):
            stub._handle_response(response)

    def test_handle_response_invalid_type(self):
        """Test handling of invalid response type."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        with pytest.raises(ValueError, match="Invalid response type"):
            stub._handle_response("not a dict")

    def test_handle_response_missing_result(self):
        """Test handling of success response without result."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        response = {"success": True, "result": None}

        with pytest.raises(ValueError, match="Response marked success but result is None"):
            stub._handle_response(response)

    def test_handle_response_invalid_base64(self):
        """Test handling of invalid base64 in result."""
        stub = LoadBalancerSlsStub(test_lb_resource)

        response = {"success": True, "result": "not_valid_base64!!!"}

        with pytest.raises(ValueError, match="Failed to deserialize result"):
            stub._handle_response(response)


class TestLoadBalancerSlsStubExecuteFunction:
    """Test suite for _execute_function method."""

    @pytest.mark.asyncio
    async def test_execute_function_no_endpoint_url(self):
        """Test error when endpoint_url is not available."""
        mock_resource = MagicMock()
        mock_resource.endpoint_url = None
        stub = LoadBalancerSlsStub(mock_resource)

        request = {"function_name": "test_func", "function_code": "def test_func(): pass"}

        with pytest.raises(ValueError, match="Endpoint URL not available"):
            await stub._execute_function(request)

    @pytest.mark.asyncio
    async def test_execute_function_timeout(self):
        """Test timeout error handling."""
        mock_resource = MagicMock()
        mock_resource.endpoint_url = "http://localhost:8000"
        stub = LoadBalancerSlsStub(mock_resource)

        request = {"function_name": "test_func", "function_code": "def test_func(): pass"}

        import httpx

        with patch("tetra_rp.stubs.load_balancer_sls.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            with pytest.raises(TimeoutError, match="Execution timeout"):
                await stub._execute_function(request)

    @pytest.mark.asyncio
    async def test_execute_function_http_error(self):
        """Test HTTP error handling."""
        mock_resource = MagicMock()
        mock_resource.endpoint_url = "http://localhost:8000"
        mock_resource.name = "test-lb"
        stub = LoadBalancerSlsStub(mock_resource)

        request = {"function_name": "test_func", "function_code": "def test_func(): pass"}

        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("tetra_rp.stubs.load_balancer_sls.httpx.AsyncClient") as mock_client:
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=error
            )

            with pytest.raises(RuntimeError, match="HTTP error from endpoint"):
                await stub._execute_function(request)


class TestLoadBalancerSlsStubCall:
    """Test suite for __call__ method."""

    @pytest.mark.asyncio
    async def test_call_success(self):
        """Test successful stub execution."""
        mock_resource = MagicMock()
        stub = LoadBalancerSlsStub(mock_resource)

        def add(x, y):
            return x + y

        with patch.object(stub, "_execute_function") as mock_execute:
            result_b64 = base64.b64encode(cloudpickle.dumps(8)).decode("utf-8")
            mock_execute.return_value = {"success": True, "result": result_b64}

            result = await stub(add, None, None, True, 5, 3)

            assert result == 8
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_with_dependencies(self):
        """Test stub execution with dependencies."""
        mock_resource = MagicMock()
        stub = LoadBalancerSlsStub(mock_resource)

        def use_requests():
            return "success"

        deps = ["requests"]

        with patch.object(stub, "_execute_function") as mock_execute:
            result_b64 = base64.b64encode(cloudpickle.dumps("success")).decode("utf-8")
            mock_execute.return_value = {"success": True, "result": result_b64}

            result = await stub(use_requests, deps, None, True)

            assert result == "success"
            # Verify dependencies were included in request
            call_args = mock_execute.call_args
            request = call_args[0][0]
            assert request["dependencies"] == deps
