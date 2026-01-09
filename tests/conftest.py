"""
Test configuration and fixtures for tetra-rp tests.

Provides shared fixtures for:
- Resource configurations (GPU, CPU)
- Mock API clients
- Test project structures
- Environment variable management
- Logger suppression
"""

import gc
import threading
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from tetra_rp.core.resources.resource_manager import ResourceManager
from tetra_rp.core.utils.singleton import SingletonMixin


@pytest.fixture
def mock_asyncio_run_coro():
    """Create a mock asyncio.run that executes coroutines."""

    def run_coro(coro):
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    return run_coro


@pytest.fixture
def sample_gpu_config() -> Dict[str, Any]:
    """Provide standard GPU configuration for tests.

    Returns:
        Dictionary with LiveServerless GPU configuration.
    """
    return {
        "name": "test_gpu_worker",
        "workersMin": 0,
        "workersMax": 3,
        "idleTimeout": 5,
    }


@pytest.fixture
def sample_cpu_config() -> Dict[str, Any]:
    """Provide standard CPU configuration for tests.

    Returns:
        Dictionary with CpuLiveServerless configuration.
    """
    return {
        "name": "test_cpu_worker",
        "workersMin": 0,
        "workersMax": 5,
        "idleTimeout": 5,
    }


@pytest.fixture
def mock_runpod_client():
    """Provide mock Runpod API client.

    Returns:
        Mock object with common Runpod API methods.
    """
    client = Mock()

    # Mock common API responses
    client.save_endpoint = AsyncMock(
        return_value={"id": "test-endpoint-id", "status": "active"}
    )
    client.get_endpoint = AsyncMock(
        return_value={"id": "test-endpoint-id", "status": "running"}
    )
    client.delete_endpoint = AsyncMock(return_value={"success": True})
    client.run_sync = AsyncMock(
        return_value={"status": "COMPLETED", "output": {"result": "success"}}
    )

    return client


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Provide temporary directory with common project structure.

    Creates a temporary directory with typical project layout:
    - main.py
    - workers/ directory
    - .env file

    Args:
        tmp_path: Pytest's built-in temporary directory fixture.

    Returns:
        Path to temporary project directory.
    """
    # Create standard project structure
    (tmp_path / "workers").mkdir()
    (tmp_path / "workers" / "__init__.py").touch()
    (tmp_path / "main.py").write_text("# Main application")
    (tmp_path / ".env").write_text("RUNPOD_API_KEY=test_key")

    return tmp_path


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """Provide patched environment variables for tests.

    Sets common environment variables needed for tests and
    returns the configuration for reference.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        Dictionary of environment variables set.
    """
    env_vars = {
        "RUNPOD_API_KEY": "test_api_key_123",
        "RUNPOD_API_BASE_URL": "https://api.runpod.io/v2",
        "LOG_LEVEL": "ERROR",  # Suppress logs during tests
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_logger():
    """Provide mock logger to suppress log output in tests.

    Returns:
        Mock logger object.
    """
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()

    return logger


@pytest.fixture
def sample_function_request() -> Dict[str, Any]:
    """Provide sample function request data for remote execution tests.

    Returns:
        Dictionary with typical function request structure.
    """
    return {
        "input": {"data": [1, 2, 3, 4, 5], "operation": "sum"},
        "timeout": 300,
        "idempotencyId": "test-request-123",
    }


@pytest.fixture
def sample_pod_template() -> Dict[str, Any]:
    """Provide sample PodTemplate configuration.

    Returns:
        Dictionary with PodTemplate configuration.
    """
    return {
        "name": "test_template",
        "imageName": "test/image:latest",
        "containerDiskInGb": 64,
        "env": {"PYTHONUNBUFFERED": "1"},
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests.

    This fixture runs automatically for all tests to ensure
    clean state between test executions.
    """
    # Patch cloudpickle to handle threading.Lock objects that may be left over
    # from previous tests. This prevents "cannot pickle '_thread.lock'" errors
    # when test pollution causes old lock instances to be in the object graph.
    try:
        import cloudpickle
        import copyreg

        def _lock_reducer(lock):
            """Reducer for threading.Lock that creates a new lock on unpickle."""
            return (threading.Lock, ())

        # Register the reducer for threading.Lock in copyreg so cloudpickle uses it
        copyreg.pickle(threading.Lock, _lock_reducer)

        # Also patch cloudpickle.CloudPickler to use the reducer
        original_reducer_override = cloudpickle.CloudPickler.reducer_override

        def patched_reducer_override(self, obj):
            if isinstance(obj, type(threading.Lock())):
                return _lock_reducer(obj)
            return original_reducer_override(self, obj)

        cloudpickle.CloudPickler.reducer_override = patched_reducer_override
    except Exception:
        # If patching fails, continue anyway - the test might still pass
        pass

    # Reset SingletonMixin instances to clear any accumulated state
    # This prevents old singleton instances from leaking into object graphs during pickling
    SingletonMixin._instances = {}

    # Also reset ResourceManager class variables to ensure clean state
    ResourceManager._resources = {}
    ResourceManager._resource_configs = {}
    ResourceManager._deployment_locks = {}
    ResourceManager._global_lock = None
    ResourceManager._lock_initialized = False
    ResourceManager._resources_initialized = False

    # Reset ResourceManager singleton if it exists
    if hasattr(ResourceManager, "_instance"):
        ResourceManager._instance = None

    # Force garbage collection to ensure old instances are truly freed
    gc.collect()

    yield

    # Cleanup after test
    SingletonMixin._instances = {}

    ResourceManager._resources = {}
    ResourceManager._resource_configs = {}
    ResourceManager._deployment_locks = {}
    ResourceManager._global_lock = None
    ResourceManager._lock_initialized = False
    ResourceManager._resources_initialized = False

    if hasattr(ResourceManager, "_instance"):
        ResourceManager._instance = None

    gc.collect()
