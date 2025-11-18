"""
Test configuration and fixtures for tetra-rp tests.

Provides shared fixtures for:
- Resource configurations (GPU, CPU)
- Mock API clients
- Test project structures
- Environment variable management
- Logger suppression
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest


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
    client.create_endpoint = AsyncMock(
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
    # Import here to avoid circular dependencies
    from tetra_rp.core.resources.resource_manager import ResourceManager

    # Reset ResourceManager singleton if it exists
    if hasattr(ResourceManager, "_instance"):
        ResourceManager._instance = None

    yield

    # Cleanup after test
    if hasattr(ResourceManager, "_instance"):
        ResourceManager._instance = None
