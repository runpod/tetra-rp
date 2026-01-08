"""HTTP utilities for RunPod API communication."""

import os
from typing import Optional

import httpx
import requests


def get_authenticated_httpx_client(
    timeout: Optional[float] = None,
) -> httpx.AsyncClient:
    """Create httpx AsyncClient with RunPod authentication.

    Automatically includes Authorization header if RUNPOD_API_KEY is set.
    This provides a centralized place to manage authentication headers for
    all RunPod HTTP requests, avoiding repetitive manual header addition.

    Args:
        timeout: Request timeout in seconds. Defaults to 30.0.

    Returns:
        Configured httpx.AsyncClient with Authorization header

    Example:
        async with get_authenticated_httpx_client() as client:
            response = await client.post(url, json=data)

        # With custom timeout
        async with get_authenticated_httpx_client(timeout=60.0) as client:
            response = await client.get(url)
    """
    headers = {}
    api_key = os.environ.get("RUNPOD_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_config = timeout if timeout is not None else 30.0
    return httpx.AsyncClient(timeout=timeout_config, headers=headers)


def get_authenticated_requests_session() -> requests.Session:
    """Create requests Session with RunPod authentication.

    Automatically includes Authorization header if RUNPOD_API_KEY is set.
    Provides a centralized place to manage authentication headers for
    synchronous RunPod HTTP requests.

    Returns:
        Configured requests.Session with Authorization header

    Example:
        session = get_authenticated_requests_session()
        response = session.post(url, json=data, timeout=30.0)
        # Remember to close: session.close()

        # Or use as context manager
        import contextlib
        with contextlib.closing(get_authenticated_requests_session()) as session:
            response = session.post(url, json=data)
    """
    session = requests.Session()
    api_key = os.environ.get("RUNPOD_API_KEY")
    if api_key:
        session.headers["Authorization"] = f"Bearer {api_key}"

    return session
