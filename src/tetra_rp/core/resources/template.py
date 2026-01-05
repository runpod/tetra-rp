import warnings
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, model_validator
from tetra_rp.core.utils.http import get_authenticated_requests_session
from .base import BaseResource


class KeyValuePair(BaseModel):
    key: str
    value: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "List[KeyValuePair]":
        """
        Create a list of KeyValuePair instances from a dictionary.
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary.")

        return [cls(key=key, value=value) for key, value in data.items()]


class PodTemplate(BaseResource):
    advancedStart: Optional[bool] = False
    config: Optional[Dict[str, Any]] = {}
    containerDiskInGb: Optional[int] = 64
    containerRegistryAuthId: Optional[str] = ""
    dockerArgs: Optional[str] = ""
    env: Optional[List[KeyValuePair]] = []
    imageName: Optional[str] = ""
    name: Optional[str] = ""
    ports: Optional[str] = ""
    startScript: Optional[str] = ""

    @model_validator(mode="after")
    def sync_input_fields(self):
        self.name = f"{self.name}__{self.resource_id}"
        return self


def update_system_dependencies(
    template_id, token=None, system_dependencies=None, base_entry_cmd=None
):
    """
    Updates Runpod template with system dependencies installed via apt-get,
    and appends the app start command.

    Args:
        template_id (str): Runpod template ID.
        token (str): [DEPRECATED] Runpod API token. Ignored; uses RUNPOD_API_KEY env var instead.
        system_dependencies (List[str]): List of apt packages to install.
        base_entry_cmd (List[str]): The default command to run the app, e.g. ["uv", "run", "handler.py"]
    Returns:
        dict: API response JSON or error info.
    """
    # Warn if deprecated token parameter is used
    if token is not None:
        warnings.warn(
            "The 'token' parameter is deprecated and ignored. "
            "Authentication now uses RUNPOD_API_KEY environment variable.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Compose apt-get install command if any packages specified
    apt_cmd = ""
    if system_dependencies:
        joined_pkgs = " ".join(system_dependencies)
        apt_cmd = f"apt-get update && apt-get install -y {joined_pkgs} && "

    # Default start command if not provided
    app_cmd = base_entry_cmd or ["uv", "run", "handler.py"]
    app_cmd_str = " ".join(app_cmd)

    # Full command to run in entrypoint shell
    full_cmd = f"{apt_cmd}exec {app_cmd_str}"

    payload = {
        # other required fields like disk, env, image, etc, should be fetched or passed in real usage
        "dockerEntrypoint": ["/bin/bash", "-c", full_cmd],
        "dockerStartCmd": [],
        # placeholder values, replace as needed or fetch from current template state
        "containerDiskInGb": 50,
        "containerRegistryAuthId": "",
        "env": {},
        "imageName": "your-image-name",
        "isPublic": False,
        "name": "your-template-name",
        "ports": ["8888/http", "22/tcp"],
        "readme": "",
        "volumeInGb": 20,
        "volumeMountPath": "/workspace",
    }

    url = f"https://rest.runpod.io/v1/templates/{template_id}/update"

    # Use centralized auth utility instead of manual header setup
    # Note: token parameter is deprecated; uses RUNPOD_API_KEY environment variable
    session = get_authenticated_requests_session()
    try:
        response = session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": "Failed to update template", "details": str(e)}
    finally:
        session.close()
