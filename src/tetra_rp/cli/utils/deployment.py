"""Deployment environment management utilities."""

import json
from typing import Dict, Any
from datetime import datetime

from tetra_rp.config import get_paths


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


def deploy_to_environment(name: str) -> Dict[str, Any]:
    """Deploy current project to environment (mock implementation)."""
    environments = get_deployment_environments()

    if name not in environments:
        raise ValueError(f"Environment {name} not found")

    # Mock deployment
    version = f"v1.{len(environments[name]['version_history'])}.0"
    url = f"https://{name.lower()}.example.com"

    # Update environment
    environments[name].update(
        {
            "status": "active",
            "current_version": version,
            "last_deployed": datetime.now().isoformat(),
            "url": url,
            "uptime": "99.9%",
        }
    )

    # Add to version history
    version_entry = {
        "version": version,
        "deployed_at": datetime.now().isoformat(),
        "description": "Deployment via CLI",
        "is_current": True,
    }

    # Mark previous versions as not current
    for v in environments[name]["version_history"]:
        v["is_current"] = False

    environments[name]["version_history"].insert(0, version_entry)

    save_deployment_environments(environments)

    return {"version": version, "url": url, "status": "active"}


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
