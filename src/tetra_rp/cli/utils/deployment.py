"""Deployment environment management utilities."""

import json
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from tetra_rp.config import get_paths
from tetra_rp.core.resources.app import FlashApp


async def upload_build(app_name: str, build_path: str | Path):
    app = await FlashApp.from_name(app_name)
    await app.upload_build(build_path)


def get_deployment_environments() -> Dict[str, Dict[str, Any]]:
    """Get all deployment environments."""
    paths = get_paths()
    deployments_file = paths.deployments_file

    if not deployments_file.exists():
        return {}

    try:
        with open(deployments_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_deployment_environments(environments: Dict[str, Dict[str, Any]]):
    """Save deployment environments to file."""
    paths = get_paths()
    deployments_file = paths.deployments_file

    # Ensure .tetra directory exists
    paths.ensure_tetra_dir()

    with open(deployments_file, "w") as f:
        json.dump(environments, f, indent=2)


def create_deployment_environment(name: str, config: Dict[str, Any]):
    """Create a new deployment environment."""
    environments = get_deployment_environments()

    # Mock environment creation
    environments[name] = {
        "status": "idle",
        "config": config,
        "created_at": datetime.now().isoformat(),
        "current_version": None,
        "last_deployed": None,
        "url": None,
        "version_history": [],
    }

    save_deployment_environments(environments)


def remove_deployment_environment(name: str):
    """Remove a deployment environment."""
    environments = get_deployment_environments()

    if name in environments:
        del environments[name]
        save_deployment_environments(environments)


async def deploy_to_environment(
    app_name: str, env_name: str, build_path: Path
) -> Dict[str, Any]:
    """Deploy current project to environment."""
    app = await FlashApp.from_name(app_name)
    try:
        await app.get_environment_by_name(env_name)
    except Exception as exc:
        text = str(exc)
        if "flash environment" in text.lower() and "not found" in text.lower():
            raise

    build = await app.upload_build(build_path)
    build_id = build["id"]

    result = await app.deploy_build_to_environment(build_id, environment_name=env_name)
    return result


def rollback_deployment(name: str, target_version: str):
    """Rollback deployment to a previous version (mock implementation)."""
    environments = get_deployment_environments()

    if name not in environments:
        raise ValueError(f"Environment {name} not found")

    # Find target version
    target_version_info = None
    for version in environments[name]["version_history"]:
        if version["version"] == target_version:
            target_version_info = version
            break

    if not target_version_info:
        raise ValueError(f"Version {target_version} not found")

    # Update current version
    environments[name]["current_version"] = target_version
    environments[name]["last_deployed"] = datetime.now().isoformat()

    # Update version history
    for version in environments[name]["version_history"]:
        version["is_current"] = version["version"] == target_version

    save_deployment_environments(environments)


def get_environment_info(name: str) -> Dict[str, Any]:
    """Get detailed information about an environment."""
    environments = get_deployment_environments()

    if name not in environments:
        raise ValueError(f"Environment {name} not found")

    env_info = environments[name].copy()

    # Add mock metrics and additional info
    if env_info["status"] == "active":
        env_info.update(
            {
                "uptime": "99.9%",
                "requests_24h": 145234,
                "avg_response_time": "245ms",
                "error_rate": "0.02%",
                "cpu_usage": "45%",
                "memory_usage": "62%",
            }
        )

    # Ensure version history exists and is properly formatted
    if "version_history" not in env_info:
        env_info["version_history"] = []

    # Add sample version history if empty
    if not env_info["version_history"] and env_info["current_version"]:
        env_info["version_history"] = [
            {
                "version": env_info["current_version"],
                "deployed_at": env_info.get(
                    "last_deployed", datetime.now().isoformat()
                ),
                "description": "Initial deployment",
                "is_current": True,
            }
        ]

    return env_info
