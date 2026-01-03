"""Deployment configuration generation for discovered handlers."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .handler_discovery import DiscoveryResult, HandlerMetadata


def generate_endpoint_config(handler: HandlerMetadata, app_name: str) -> dict[str, Any]:
    """Generate serverless endpoint configuration from handler metadata.

    Args:
        handler: Handler metadata from discovery
        app_name: Application name

    Returns:
        Dict containing endpoint configuration ready for deployment
    """
    # Generate unique endpoint name
    endpoint_name = f"{app_name}-{handler.handler_id}"

    # Extract serverless config parameters
    serverless_params = handler.serverless_config.get("serverless", {})

    # Build endpoint configuration
    endpoint_config = {
        "name": endpoint_name,
        "type": _map_handler_type_to_serverless_type(handler.handler_type),
        "workersMin": serverless_params.get("workersMin", 0),
        "workersMax": serverless_params.get("workersMax", 3),
        "idleTimeout": serverless_params.get("idleTimeout", 5),
    }

    # Add GPU-specific or CPU-specific configuration
    if handler.compute_type == "cpu":
        # CPU configuration
        instance_ids = serverless_params.get("instanceIds", ["cpu5g-2-8"])
        endpoint_config["instanceIds"] = instance_ids
    else:
        # GPU configuration (default)
        gpus = serverless_params.get("gpus", ["NVIDIA A40"])
        endpoint_config["gpus"] = gpus
        endpoint_config["gpuCount"] = serverless_params.get("gpuCount", 1)

    # Generate environment variables for handler identification
    env_vars = _generate_handler_env_vars(handler)

    # Build complete handler deployment config
    return {
        "handler_id": handler.handler_id,
        "handler_type": handler.handler_type,
        "compute_type": handler.compute_type,
        "resource_class": handler.resource_class
        or _infer_resource_class(handler.compute_type),
        "endpoint_config": endpoint_config,
        "environment_vars": env_vars,
        "routes": handler.routes,
        "source_file": handler.source_file,
        "source_router": handler.source_router,
    }


def _map_handler_type_to_serverless_type(handler_type: str) -> str:
    """Map handler type to Runpod serverless type.

    Args:
        handler_type: "queue" or "load_balancer"

    Returns:
        "QB" for queue-based, "LB" for load-balancer
    """
    return "QB" if handler_type == "queue" else "LB"


def _infer_resource_class(compute_type: str) -> str:
    """Infer resource class name from compute type.

    Args:
        compute_type: "gpu" or "cpu"

    Returns:
        Resource class name
    """
    return "CpuLiveServerless" if compute_type == "cpu" else "LiveServerless"


def _generate_handler_env_vars(handler: HandlerMetadata) -> dict[str, str]:
    """Generate environment variables for handler identification.

    These env vars are used by the deployed endpoint to determine which
    handler to activate from the tarball.

    Args:
        handler: Handler metadata

    Returns:
        Dict of environment variables
    """
    # Serialize routes as JSON string for env var
    routes_json = json.dumps(
        [{"path": r["path"], "method": r["method"]} for r in handler.routes]
    )

    return {
        "HANDLER_ID": handler.handler_id,
        "HANDLER_TYPE": handler.handler_type,
        "HANDLER_ROUTES": routes_json,
        "HANDLER_SOURCE_FILE": handler.source_file,
        "HANDLER_SOURCE_ROUTER": handler.source_router or "",
    }


def generate_deployment_manifest(
    discovery_result: DiscoveryResult, app_name: str, build_dir: Path
) -> dict[str, Any]:
    """Generate complete deployment manifest for all handlers.

    Args:
        discovery_result: Handler discovery result
        app_name: Application name
        build_dir: Path to build directory

    Returns:
        Complete deployment manifest
    """
    # Generate endpoint configs for all handlers
    handler_configs = [
        generate_endpoint_config(handler, app_name)
        for handler in discovery_result.handlers
    ]

    # Build deployment manifest
    manifest = {
        "version": "1.0",
        "app_name": app_name,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "build_dir": str(build_dir),
        "handlers": handler_configs,
        "discovery_warnings": discovery_result.warnings,
        "stats": discovery_result.stats,
    }

    return manifest


def write_deployment_manifest(manifest: dict[str, Any], build_dir: Path) -> Path:
    """Write deployment manifest to build directory.

    Args:
        manifest: Deployment manifest to write
        build_dir: Path to build directory

    Returns:
        Path to written manifest file
    """
    manifest_path = build_dir / ".flash_deployment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


def read_deployment_manifest(manifest_path: Path) -> dict[str, Any]:
    """Read deployment manifest from file.

    Args:
        manifest_path: Path to manifest file

    Returns:
        Deployment manifest dict
    """
    return json.loads(manifest_path.read_text())
