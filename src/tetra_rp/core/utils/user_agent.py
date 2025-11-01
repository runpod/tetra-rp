"""User-Agent utilities for Tetra HTTP clients."""

import platform
from importlib import metadata


def get_tetra_user_agent() -> str:
    """
    Generate Tetra User-Agent string for HTTP requests.

    Format: Runpod-Tetra/<version> (<OS> <release>; <arch>) Language/Python <python_version>
    Example: Runpod-Tetra/0.4.2 (Linux 6.8.0-49-generic; x86_64) Language/Python 3.10.12

    Returns:
        str: Formatted User-Agent string
    """
    try:
        tetra_version = metadata.version("tetra_rp")
    except metadata.PackageNotFoundError:
        tetra_version = "unknown"

    # Get system information
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    python_version = platform.python_version()

    # Format User-Agent string
    user_agent = f"Runpod-Tetra/{tetra_version} ({system} {release}; {machine}) Language/Python {python_version}"

    return user_agent
